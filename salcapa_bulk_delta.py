"""Checkpointed, folder-scoped discovery for the SalCAPA enterprise intake.

The cursor and item ledger share one database transaction per Graph page. No
source bytes are downloaded here. Processing is a separate, gated step.
"""

from __future__ import annotations

import json
import time
import uuid
from urllib.parse import urlparse

from salcapa_m365_intake import GRAPH_ROOT, M365IntakeError, _IDENTIFIER


SELECT = "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,cTag,createdBy,lastModifiedBy,webUrl,parentReference,deleted"


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_bulk_cursors (
      drive_id TEXT NOT NULL, pending_id TEXT NOT NULL,
      link TEXT NOT NULL DEFAULT '', phase TEXT NOT NULL DEFAULT 'initial',
      lease_owner TEXT NOT NULL DEFAULT '', lease_until INTEGER NOT NULL DEFAULT 0,
      next_attempt INTEGER NOT NULL DEFAULT 0, last_error TEXT NOT NULL DEFAULT '',
      generation INTEGER NOT NULL DEFAULT 0,
      updated_at INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(drive_id,pending_id)
    );
    CREATE TABLE IF NOT EXISTS m365_bulk_items (
      drive_id TEXT NOT NULL, pending_id TEXT NOT NULL, item_id TEXT NOT NULL,
      parent_id TEXT NOT NULL DEFAULT '', name TEXT NOT NULL DEFAULT '',
      kind TEXT NOT NULL, etag TEXT NOT NULL DEFAULT '', size BIGINT NOT NULL DEFAULT 0,
      metadata_json TEXT NOT NULL DEFAULT '{}', status TEXT NOT NULL,
      reason TEXT NOT NULL DEFAULT '', attempts INTEGER NOT NULL DEFAULT 0,
      next_attempt INTEGER NOT NULL DEFAULT 0, updated_at INTEGER NOT NULL,
      seen_generation INTEGER NOT NULL DEFAULT 0,
      lease_owner TEXT NOT NULL DEFAULT '', lease_until INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(drive_id,pending_id,item_id)
    );
    CREATE INDEX IF NOT EXISTS idx_m365_bulk_work
      ON m365_bulk_items(drive_id,pending_id,status,next_attempt,updated_at);
    """)
    # Existing PostgreSQL ledgers were created with a 32-bit size column.
    # Graph reports folder sizes beyond that range even though byte processing
    # remains capped separately. Migrate in place before the first page insert.
    if getattr(conn, "backend", "") == "postgres":
        row = conn.execute(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema=current_schema() AND table_name='m365_bulk_items' "
            "AND column_name='size'"
        ).fetchone()
        if row is None:
            raise M365IntakeError("Bulk ledger size column is missing")
        if row["data_type"] == "integer":
            conn.execute("ALTER TABLE m365_bulk_items ALTER COLUMN size TYPE BIGINT")
        elif row["data_type"] != "bigint":
            raise M365IntakeError("Bulk ledger size column has an unsupported type")


def _scoped_link(link, drive_id, pending_id):
    if not isinstance(link, str) or not link or len(link) > 8192:
        raise M365IntakeError("Graph change continuation is invalid")
    parsed = urlparse(link)
    path = f"/v1.0/drives/{drive_id}/items/{pending_id}/delta"
    if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
            or parsed.path != path or not parsed.query or parsed.fragment):
        raise M365IntakeError("Graph change continuation left the governed folder")
    return link


def resolve_pending(intake):
    """Resolve the one named pending folder from the configured intake root."""
    root = f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{intake.config.folder_item_id}/children"
    page, params, seen, matches = root, {"$select": "id,name,folder,remoteItem", "$top": "200"}, set(), []
    while page:
        if page in seen or len(seen) >= 100:
            raise M365IntakeError("Pending folder pagination did not terminate")
        seen.add(page)
        response = intake.client.get(page, headers=intake._headers(), params=params)
        if response.status_code != 200:
            raise M365IntakeError("Pending folder could not be resolved")
        payload = response.json()
        if not isinstance(payload.get("value"), list):
            raise M365IntakeError("Pending folder response was incomplete")
        for item in payload["value"]:
            if not isinstance(item, dict):
                raise M365IntakeError("Pending folder response was invalid")
            if item.get("name") == "10 Pending Classification":
                if "remoteItem" in item or not isinstance(item.get("folder"), dict):
                    raise M365IntakeError("Pending folder identity is invalid")
                matches.append(str(item.get("id", "")))
        next_link = payload.get("@odata.nextLink")
        if next_link:
            parsed = urlparse(next_link)
            if (not isinstance(next_link, str) or len(next_link) > 8192
                    or parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                    or parsed.path != urlparse(root).path or not parsed.query or parsed.fragment):
                raise M365IntakeError("Pending folder pagination left the governed root")
        page, params = next_link, None
    if len(matches) != 1 or not _IDENTIFIER.fullmatch(matches[0]):
        raise M365IntakeError("Pending folder was not uniquely resolved")
    return matches[0]


def _claim(conn, drive, pending, clock):
    owner = uuid.uuid4().hex
    conn.execute(
        "INSERT INTO m365_bulk_cursors(drive_id,pending_id) VALUES(?,?) "
        "ON CONFLICT(drive_id,pending_id) DO NOTHING", (drive, pending),
    )
    cursor = conn.execute(
        "UPDATE m365_bulk_cursors SET lease_owner=?,lease_until=? "
        "WHERE drive_id=? AND pending_id=? AND lease_until<? AND next_attempt<=? "
        "RETURNING link,phase,generation",
        (owner, clock + 120, drive, pending, clock, clock),
    ).fetchone()
    conn.commit()
    return (owner, cursor) if cursor else (None, None)


def _apply_item(conn, intake, pending, item, clock, generation):
    if not isinstance(item, dict) or not _IDENTIFIER.fullmatch(str(item.get("id", ""))):
        raise M365IntakeError("Graph change item identity is invalid")
    item_id = item["id"]
    deleted = "deleted" in item
    if deleted:
        conn.execute(
            "UPDATE m365_bulk_items SET status='Removed',reason='source_deleted',updated_at=? "
      "WHERE drive_id=? AND pending_id=? AND item_id=?",
            (clock, intake.config.drive_id, pending, item_id),
        )
        return
    if "remoteItem" in item:
        raise M365IntakeError("Graph change feed contained a shortcut")
    kind = "folder" if "folder" in item else "file" if "file" in item else "other"
    name = intake._safe_path_component(item.get("name"))
    parent = str((item.get("parentReference") or {}).get("id", ""))
    if parent and not _IDENTIFIER.fullmatch(parent):
        raise M365IntakeError("Graph change parent identity is invalid")
    if item_id != pending and not parent:
        raise M365IntakeError("Graph change item parent is missing")
    size = int(item.get("size", 0))
    if size < 0:
        raise M365IntakeError("Graph change item size is invalid")
    etag = str(item.get("eTag", ""))[:512]
    if kind == "file" and (not etag or not item.get("lastModifiedDateTime")):
        raise M365IntakeError("Graph change item provenance is incomplete")
    if kind == "file" and size > intake.config.max_file_bytes:
        status, reason = "Oversize", "file_size_limit"
    elif kind == "file":
        status, reason = "Pending", ""
    else:
        status, reason = "Directory", ""
    metadata = {
        "mime_type": str((item.get("file") or {}).get("mimeType", ""))[:255],
        "last_modified": str(item.get("lastModifiedDateTime", ""))[:64],
        "ctag": str(item.get("cTag", ""))[:512],
        "source_owner": intake._identity(item.get("createdBy"))[0],
        "source_owner_id": intake._identity(item.get("createdBy"))[1],
        "last_modified_by": intake._identity(item.get("lastModifiedBy"))[0],
        "web_url": intake._trusted_source_url(item.get("webUrl")),
    }
    conn.execute(
        """INSERT INTO m365_bulk_items
        (drive_id,pending_id,item_id,parent_id,name,kind,etag,size,metadata_json,status,reason,updated_at,seen_generation)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(drive_id,pending_id,item_id) DO UPDATE SET
          parent_id=excluded.parent_id,name=excluded.name,kind=excluded.kind,
          etag=excluded.etag,size=excluded.size,metadata_json=excluded.metadata_json,
          status=CASE WHEN m365_bulk_items.etag=excluded.etag AND
                           m365_bulk_items.parent_id=excluded.parent_id AND
                           m365_bulk_items.name=excluded.name AND
                           m365_bulk_items.status IN ('Done','Retry','Working')
                      THEN m365_bulk_items.status ELSE excluded.status END,
          reason=excluded.reason,
          attempts=CASE WHEN m365_bulk_items.etag=excluded.etag
                        THEN m365_bulk_items.attempts ELSE 0 END,
          lease_owner=CASE WHEN m365_bulk_items.etag=excluded.etag
                           THEN m365_bulk_items.lease_owner ELSE '' END,
          lease_until=CASE WHEN m365_bulk_items.etag=excluded.etag
                           THEN m365_bulk_items.lease_until ELSE 0 END,
          updated_at=excluded.updated_at,seen_generation=excluded.seen_generation""",
        (intake.config.drive_id,pending,item_id,parent,name,kind,etag,size,
         json.dumps(metadata,sort_keys=True),status,reason,clock,generation),
    )


def discover(intake, connect, *, max_pages=10, now=None):
    """Commit each page and its continuation together; one scanner owns the cursor."""
    clock = int(time.time() if now is None else now)
    pending = resolve_pending(intake)
    drive = intake.config.drive_id
    conn = connect()
    owner = None
    try:
        create_tables(conn)
        owner, cursor = _claim(conn, drive, pending, clock)
        if not owner:
            return {"pages": 0, "busy": True}
        link = cursor["link"]
        phase = cursor["phase"]
        generation = cursor["generation"]
        endpoint = f"{GRAPH_ROOT}/drives/{drive}/items/{pending}/delta"
        pages = 0
        for _ in range(max_pages):
            url = _scoped_link(link, drive, pending) if link else endpoint
            response = intake.client.get(url, headers=intake._headers(),
                                         params=None if link else {"$select": SELECT, "$top": "200"})
            if response.status_code == 410:
                # Retain ledger history; restart a full delta representation.
                conn.execute("UPDATE m365_bulk_cursors SET link='',phase='resync',generation=generation+1,lease_until=0,"
                             "lease_owner='',last_error='delta_resync' WHERE drive_id=? AND pending_id=? "
                             "AND lease_owner=?", (drive,pending,owner))
                conn.commit()
                return {"pages": pages, "resync": True}
            if response.status_code in (429,503):
                retry = response.headers.get("Retry-After", "")
                delay = min(3600,max(1,int(retry))) if retry.isdigit() else 60
                conn.execute("UPDATE m365_bulk_cursors SET next_attempt=?,lease_until=0,"
                             "lease_owner='',last_error='graph_throttled' WHERE drive_id=? "
                             "AND pending_id=? AND lease_owner=?", (clock+delay,drive,pending,owner))
                conn.commit()
                return {"pages": pages, "throttled": True}
            if response.status_code != 200:
                raise M365IntakeError("Graph change feed unavailable")
            payload = response.json()
            values = payload.get("value")
            next_link = payload.get("@odata.nextLink")
            delta_link = payload.get("@odata.deltaLink")
            if (not isinstance(values,list) or bool(next_link)==bool(delta_link)
                    or len(values)>1000):
                raise M365IntakeError("Graph change page was incomplete")
            link = _scoped_link(next_link or delta_link,drive,pending)
            for item in values:
                _apply_item(conn,intake,pending,item,clock,generation)
            if delta_link and phase == "resync":
                conn.execute("UPDATE m365_bulk_items SET status='Removed',reason='absent_after_resync',"
                             "updated_at=? WHERE drive_id=? AND pending_id=? AND seen_generation<>? "
                             "AND status<>'Removed'",(clock,drive,pending,generation))
            phase = "delta" if delta_link else "initial" if phase == "initial" else phase
            updated = conn.execute(
                "UPDATE m365_bulk_cursors SET link=?,phase=?,updated_at=?,lease_until=?,"
                "last_error='' WHERE drive_id=? AND pending_id=? AND lease_owner=?",
                (link,phase,clock,clock+120,drive,pending,owner),
            )
            if updated.rowcount != 1:
                conn.rollback()
                raise M365IntakeError("Graph change lease was lost")
            conn.commit()
            pages += 1
            if delta_link:
                break
        conn.execute("UPDATE m365_bulk_cursors SET lease_until=0,lease_owner='' "
                     "WHERE drive_id=? AND pending_id=? AND lease_owner=?",(drive,pending,owner))
        conn.commit()
        return {"pages":pages,"complete":phase=="delta"}
    except Exception:
        conn.rollback()
        if owner:
            try:
                conn.execute(
                    "UPDATE m365_bulk_cursors SET lease_until=0,lease_owner='',"
                    "next_attempt=?,last_error='delta_discovery_error' "
                    "WHERE drive_id=? AND pending_id=? AND lease_owner=?",
                    (clock + 60, drive, pending, owner),
                )
                conn.commit()
            except Exception:
                conn.rollback()
        raise
    finally:
        conn.close()


def checkpoint_oversize(connect, drive, pending, items, *, now=None):
    """Retain legacy scanner size holds without reading bytes or claiming work.

    The legacy listing remains bounded; this checkpoints only files actually
    seen in its pass. The full delta scan separately discovers the full tree.
    """
    if not _IDENTIFIER.fullmatch(drive) or not _IDENTIFIER.fullmatch(pending):
        raise M365IntakeError("Oversize checkpoint scope is invalid")
    clock = int(time.time() if now is None else now)
    conn = connect()
    try:
        create_tables(conn)
        for item in items:
            item_id = str(item.get("id", ""))
            parent = str(item.get("parent_id", ""))
            if (not _IDENTIFIER.fullmatch(item_id)
                    or not _IDENTIFIER.fullmatch(parent)
                    or not item.get("etag") or int(item.get("size", -1)) < 0):
                raise M365IntakeError("Oversize source metadata is incomplete")
            metadata = {key: item.get(key, "") for key in (
                "relative_path", "mime_type", "last_modified", "ctag",
                "source_owner", "source_owner_id", "last_modified_by", "web_url",
            )}
            conn.execute(
                """INSERT INTO m365_bulk_items
                (drive_id,pending_id,item_id,parent_id,name,kind,etag,size,
                 metadata_json,status,reason,updated_at)
                VALUES(?,?,?,?,?,'file',?,?,?,'Oversize','file_size_limit',?)
                ON CONFLICT(drive_id,pending_id,item_id) DO UPDATE SET
                  parent_id=excluded.parent_id,name=excluded.name,etag=excluded.etag,
                  size=excluded.size,metadata_json=excluded.metadata_json,
                  status=CASE WHEN m365_bulk_items.etag=excluded.etag
                                   AND m365_bulk_items.status='Done'
                              THEN 'Done' ELSE 'Oversize' END,
                  reason=CASE WHEN m365_bulk_items.etag=excluded.etag
                                   AND m365_bulk_items.status='Done'
                              THEN m365_bulk_items.reason ELSE 'file_size_limit' END,
                  updated_at=excluded.updated_at""",
                (drive,pending,item_id,parent,str(item.get("name", ""))[:512],
                 str(item["etag"])[:512],int(item["size"]),
                 json.dumps(metadata,sort_keys=True),clock),
            )
        conn.commit()
        return len(items)
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def claim_work(connect, drive, pending, *, limit=20, now=None):
    """Lease due files in oldest-first order across competing worker replicas."""
    if not 1 <= limit <= 100:
        raise ValueError("Work batch limit is out of range")
    clock = int(time.time() if now is None else now)
    conn = connect()
    selected = []
    try:
        for _ in range(limit):
            owner = uuid.uuid4().hex
            row = conn.execute(
                """UPDATE m365_bulk_items SET status='Working',lease_owner=?,
                   lease_until=?,attempts=attempts+1
                   WHERE drive_id=? AND pending_id=? AND item_id=(
                     SELECT item_id FROM m365_bulk_items
                     WHERE drive_id=? AND pending_id=? AND kind='file'
                       AND ((status IN ('Pending','Retry') AND next_attempt<=?)
                         OR (status='Working' AND lease_until<?))
                     ORDER BY updated_at,item_id LIMIT 1
                   ) AND ((status IN ('Pending','Retry') AND next_attempt<=?)
                         OR (status='Working' AND lease_until<?))
                   RETURNING item_id,parent_id,name,etag,size,metadata_json,
                             attempts,lease_owner""",
                (owner,clock+300,drive,pending,drive,pending,clock,clock,clock,clock),
            ).fetchone()
            if row is None:
                conn.commit()
                break
            conn.commit()
            metadata = json.loads(row["metadata_json"])
            selected.append(dict(metadata,id=row["item_id"],parent_id=row["parent_id"],
                                 name=row["name"],etag=row["etag"],size=row["size"],
                                 attempts=row["attempts"],lease_owner=row["lease_owner"]))
        return selected
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def complete_work(connect, drive, pending, item, *, success, reason="", hold=False, now=None):
    """Commit a version-bound outcome; a changed ETag cannot inherit success."""
    clock = int(time.time() if now is None else now)
    attempts = item["attempts"]
    delay = 0 if success or hold else min(3600, 30 * (2 ** min(attempts - 1, 7)))
    conn = connect()
    try:
        cursor = conn.execute(
            """UPDATE m365_bulk_items SET status=?,reason=?,next_attempt=?,
               lease_owner='',lease_until=0,updated_at=?
               WHERE drive_id=? AND pending_id=? AND item_id=? AND etag=?
                 AND lease_owner=? AND status='Working'""",
            ("Assignment Required" if hold else "Done" if success else "Retry",
             reason[:120],clock+delay,clock,
             drive,pending,item["id"],item["etag"],item["lease_owner"]),
        )
        conn.commit()
        return cursor.rowcount == 1
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
