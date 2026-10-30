"""Metadata-only reconciliation for the governed ``Does Not Upload`` area.

The release records every current source item as a governed hold with explicit
research, teaching, and citation review dispositions.  It never downloads
source bytes and emits aggregate counts only.
"""

from __future__ import annotations

import json
import re
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlparse

from database import connect_database


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
EXPECTED_HOLD_FILES = 93
MAX_ITEMS = 1_000
MAX_FOLDERS = 100
MAX_PAGES = 100
SOURCE_AREA = "Does Not Upload"
HOLD_REASON = "source_area_does_not_upload"
REVIEW_REQUIRED = "Review Required"
SOURCE_AREAS = {
    "10 Pending Classification",
    "20 Ready for Intake Review",
    "30 Exceptions and Manual Review",
    "40 Customer Batch Staging - Unassigned",
    "90 Migration Hold",
    "90 Processed Intake",
    SOURCE_AREA,
}
IDENTIFIER = re.compile(r"[A-Za-z0-9_!.-]{8,256}")


def _scoped_children_link(link: object, endpoint: str) -> str:
    if not isinstance(link, str) or not link or len(link) > 8192:
        raise RuntimeError("Hold continuation invalid")
    parsed, expected = urlparse(link), urlparse(endpoint)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "graph.microsoft.com"
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.path != expected.path
        or not parsed.query
    ):
        raise RuntimeError("Hold continuation left the governed folder")
    return link


def _children(intake: Any, folder_id: str) -> tuple[list[dict[str, Any]], int]:
    endpoint = f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{folder_id}/children"
    page, params, seen, items = endpoint, {
        "$select": (
            "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,"
            "createdBy,lastModifiedBy,webUrl,parentReference"
        ),
        "$top": "200",
    }, set(), []
    pages = 0
    while page:
        if page in seen or pages >= MAX_PAGES:
            raise RuntimeError("Hold pagination did not terminate")
        seen.add(page)
        pages += 1
        response = intake.client.get(page, headers=intake._headers(), params=params)
        if response.status_code != 200:
            raise RuntimeError("Hold source folder unavailable")
        payload = response.json()
        values = payload.get("value")
        if not isinstance(values, list) or len(values) > 1_000:
            raise RuntimeError("Hold source response invalid")
        items.extend(values)
        next_page = payload.get("@odata.nextLink")
        page = _scoped_children_link(next_page, endpoint) if next_page else ""
        params = None
    return items, pages


def _safe_component(value: object) -> str:
    text = str(value or "")
    if not text or text in {".", ".."} or "/" in text or "\\" in text:
        raise RuntimeError("Hold source name invalid")
    return text


def inventory(intake: Any) -> list[dict[str, Any]]:
    root_items, pages = _children(intake, intake.config.folder_item_id)
    top_level: dict[str, str] = {}
    for item in root_items:
        if not isinstance(item, dict) or "remoteItem" in item:
            raise RuntimeError("Hold root item invalid")
        name = _safe_component(item.get("name"))
        item_id = str(item.get("id", ""))
        parent = str((item.get("parentReference") or {}).get("id", ""))
        if (
            not IDENTIFIER.fullmatch(item_id)
            or parent != intake.config.folder_item_id
            or not isinstance(item.get("folder"), dict)
            or isinstance(item.get("file"), dict)
        ):
            raise RuntimeError("Hold root folder identity invalid")
        top_level[name] = item_id
    if set(top_level) != SOURCE_AREAS:
        raise RuntimeError("Hold source-area boundary changed")

    queue = deque([(top_level[SOURCE_AREA], SOURCE_AREA)])
    seen_folders, seen_items, files = set(), set(), []
    while queue:
        folder_id, relative_folder = queue.popleft()
        if folder_id in seen_folders or len(seen_folders) >= MAX_FOLDERS:
            raise RuntimeError("Hold folder traversal invalid")
        seen_folders.add(folder_id)
        children, child_pages = _children(intake, folder_id)
        pages += child_pages
        if pages > MAX_PAGES:
            raise RuntimeError("Hold page limit exceeded")
        for item in children:
            if not isinstance(item, dict) or "remoteItem" in item:
                raise RuntimeError("Hold source item invalid")
            item_id = str(item.get("id", ""))
            parent = str((item.get("parentReference") or {}).get("id", ""))
            if (
                not IDENTIFIER.fullmatch(item_id)
                or item_id in seen_items
                or parent != folder_id
            ):
                raise RuntimeError("Hold source identity invalid")
            seen_items.add(item_id)
            if len(seen_items) > MAX_ITEMS:
                raise RuntimeError("Hold source item limit exceeded")
            name = _safe_component(item.get("name"))
            relative_path = f"{relative_folder}/{name}"
            is_folder = isinstance(item.get("folder"), dict)
            is_file = isinstance(item.get("file"), dict)
            if is_folder == is_file:
                raise RuntimeError("Hold source item kind invalid")
            if is_folder:
                queue.append((item_id, relative_path))
                continue
            size = item.get("size")
            etag = str(item.get("eTag", ""))
            modified = str(item.get("lastModifiedDateTime", ""))
            if not isinstance(size, int) or size < 0 or not etag or not modified:
                raise RuntimeError("Hold source provenance incomplete")
            source_owner, source_owner_id = intake._identity(item.get("createdBy"))
            files.append({
                "source_item_id": item_id,
                "source_parent_id": parent,
                "source_name": name,
                "source_relative_path": relative_path,
                "source_etag": etag[:512],
                "source_size": size,
                "source_modified_at": modified[:64],
                "source_owner": source_owner,
                "source_owner_id": source_owner_id,
                "source_web_url": intake._trusted_source_url(item.get("webUrl")),
            })
    if len(files) != EXPECTED_HOLD_FILES:
        raise RuntimeError("Hold source file count changed")
    return files


def _create_tables(conn: Any) -> None:
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_knowledge_holds (
      source_drive_id TEXT NOT NULL,
      source_item_id TEXT NOT NULL,
      source_parent_id TEXT NOT NULL,
      source_name TEXT NOT NULL,
      source_relative_path TEXT NOT NULL,
      source_etag TEXT NOT NULL,
      source_size BIGINT NOT NULL,
      source_modified_at TEXT NOT NULL,
      source_owner TEXT NOT NULL DEFAULT '',
      source_owner_id TEXT NOT NULL DEFAULT '',
      source_web_url TEXT NOT NULL DEFAULT '',
      source_area TEXT NOT NULL,
      status TEXT NOT NULL,
      hold_reason TEXT NOT NULL,
      research_disposition TEXT NOT NULL,
      teaching_disposition TEXT NOT NULL,
      citation_disposition TEXT NOT NULL,
      reviewed_by TEXT NOT NULL DEFAULT '',
      reviewed_at TEXT NOT NULL DEFAULT '',
      review_rationale TEXT NOT NULL DEFAULT '',
      discovered_at TEXT NOT NULL,
      last_seen_at TEXT NOT NULL,
      PRIMARY KEY(source_drive_id,source_item_id)
    );
    CREATE TABLE IF NOT EXISTS m365_knowledge_hold_events (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      source_drive_id TEXT NOT NULL,
      source_item_id TEXT NOT NULL,
      event_type TEXT NOT NULL,
      actor TEXT NOT NULL,
      detail_json TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_m365_knowledge_holds_state
      ON m365_knowledge_holds(source_area,status,research_disposition,
                              teaching_disposition,citation_disposition);
    """)


def _event(conn: Any, drive_id: str, item_id: str, event_type: str,
           detail: dict[str, Any], timestamp: str) -> None:
    conn.execute(
        "INSERT INTO m365_knowledge_hold_events"
        "(source_drive_id,source_item_id,event_type,actor,detail_json,created_at) "
        "VALUES(?,?,?,?,?,?)",
        (drive_id, item_id, event_type, "salcapa-governed-hold-worker",
         json.dumps(detail, sort_keys=True), timestamp),
    )


def reconcile(intake: Any, connect: Callable[[], Any] = connect_database) -> dict[str, int]:
    files = inventory(intake)
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    drive_id = intake.config.drive_id
    source_ids = {row["source_item_id"] for row in files}
    conn = connect()
    inserted = changed = refreshed = removed = events = 0
    try:
        _create_tables(conn)
        for row in files:
            existing = conn.execute(
                "SELECT source_etag,status FROM m365_knowledge_holds "
                "WHERE source_drive_id=? AND source_item_id=?",
                (drive_id, row["source_item_id"]),
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO m365_knowledge_holds
                    (source_drive_id,source_item_id,source_parent_id,source_name,
                     source_relative_path,source_etag,source_size,source_modified_at,
                     source_owner,source_owner_id,source_web_url,source_area,status,
                     hold_reason,research_disposition,teaching_disposition,
                     citation_disposition,discovered_at,last_seen_at)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        drive_id, row["source_item_id"], row["source_parent_id"],
                        row["source_name"], row["source_relative_path"], row["source_etag"],
                        row["source_size"], row["source_modified_at"], row["source_owner"],
                        row["source_owner_id"], row["source_web_url"], SOURCE_AREA,
                        "Governed Hold", HOLD_REASON, REVIEW_REQUIRED, REVIEW_REQUIRED,
                        REVIEW_REQUIRED, timestamp, timestamp,
                    ),
                )
                _event(conn, drive_id, row["source_item_id"], "HoldRecorded", {
                    "source_area": SOURCE_AREA,
                    "source_etag": row["source_etag"],
                    "source_size": row["source_size"],
                    "source_modified_at": row["source_modified_at"],
                }, timestamp)
                inserted += 1
                events += 1
                continue
            version_changed = str(existing["source_etag"]) != row["source_etag"]
            if version_changed:
                conn.execute(
                    """UPDATE m365_knowledge_holds SET
                    source_parent_id=?,source_name=?,source_relative_path=?,source_etag=?,
                    source_size=?,source_modified_at=?,source_owner=?,source_owner_id=?,
                    source_web_url=?,status='Governed Hold',hold_reason=?,
                    research_disposition=?,teaching_disposition=?,citation_disposition=?,
                    reviewed_by='',reviewed_at='',review_rationale='',last_seen_at=?
                    WHERE source_drive_id=? AND source_item_id=?""",
                    (
                        row["source_parent_id"], row["source_name"],
                        row["source_relative_path"], row["source_etag"], row["source_size"],
                        row["source_modified_at"], row["source_owner"], row["source_owner_id"],
                        row["source_web_url"], HOLD_REASON, REVIEW_REQUIRED, REVIEW_REQUIRED,
                        REVIEW_REQUIRED, timestamp, drive_id, row["source_item_id"],
                    ),
                )
                _event(conn, drive_id, row["source_item_id"], "HoldSourceVersionChanged", {
                    "prior_source_etag": str(existing["source_etag"]),
                    "source_etag": row["source_etag"],
                    "source_size": row["source_size"],
                    "source_modified_at": row["source_modified_at"],
                }, timestamp)
                changed += 1
                events += 1
            else:
                conn.execute(
                    """UPDATE m365_knowledge_holds SET
                    source_parent_id=?,source_name=?,source_relative_path=?,source_size=?,
                    source_modified_at=?,source_owner=?,source_owner_id=?,source_web_url=?,
                    last_seen_at=? WHERE source_drive_id=? AND source_item_id=?""",
                    (
                        row["source_parent_id"], row["source_name"],
                        row["source_relative_path"], row["source_size"],
                        row["source_modified_at"], row["source_owner"], row["source_owner_id"],
                        row["source_web_url"], timestamp, drive_id, row["source_item_id"],
                    ),
                )
                refreshed += 1

        active_rows = conn.execute(
            "SELECT source_item_id FROM m365_knowledge_holds "
            "WHERE source_drive_id=? AND source_area=? AND status<>'Source Removed'",
            (drive_id, SOURCE_AREA),
        ).fetchall()
        for existing in active_rows:
            item_id = str(existing["source_item_id"])
            if item_id in source_ids:
                continue
            conn.execute(
                """UPDATE m365_knowledge_holds SET status='Source Removed',
                research_disposition='Not Available',teaching_disposition='Not Available',
                citation_disposition='Not Available',last_seen_at=?
                WHERE source_drive_id=? AND source_item_id=?""",
                (timestamp, drive_id, item_id),
            )
            _event(conn, drive_id, item_id, "HoldSourceRemoved", {
                "source_area": SOURCE_AREA,
            }, timestamp)
            removed += 1
            events += 1

        active = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_holds WHERE source_drive_id=? "
            "AND source_area=? AND status='Governed Hold'",
            (drive_id, SOURCE_AREA),
        ).fetchone()[0])
        research_review = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_holds WHERE source_drive_id=? "
            "AND source_area=? AND status='Governed Hold' AND research_disposition=?",
            (drive_id, SOURCE_AREA, REVIEW_REQUIRED),
        ).fetchone()[0])
        teaching_review = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_holds WHERE source_drive_id=? "
            "AND source_area=? AND status='Governed Hold' AND teaching_disposition=?",
            (drive_id, SOURCE_AREA, REVIEW_REQUIRED),
        ).fetchone()[0])
        citation_review = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_holds WHERE source_drive_id=? "
            "AND source_area=? AND status='Governed Hold' AND citation_disposition=?",
            (drive_id, SOURCE_AREA, REVIEW_REQUIRED),
        ).fetchone()[0])
        if active != EXPECTED_HOLD_FILES:
            raise RuntimeError("Governed hold reconciliation is incomplete")
        conn.commit()
        return {
            "source_files": len(files),
            "inserted": inserted,
            "changed": changed,
            "refreshed": refreshed,
            "removed": removed,
            "events_added": events,
            "active_holds": active,
            "research_review_required": research_review,
            "teaching_review_required": teaching_review,
            "citation_review_required": citation_review,
            "content_downloads": 0,
            "hold_reconciliation_complete": int(active == len(files)),
        }
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake

    intake = GovernedM365Intake(GovernedM365Config.from_environment())
    result = reconcile(intake)
    for key in sorted(result):
        print(f"HOLD_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
