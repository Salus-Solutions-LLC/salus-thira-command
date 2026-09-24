"""Durable, default-off customer batch assignments.

This ledger records ownership before a customer source can be routed. It has no
Graph write or enterprise promotion path; the release worker must separately
verify the live source, destination permissions, and byte hashes.
"""

from __future__ import annotations

import re
import time
import uuid


_ID = re.compile(r"[A-Za-z0-9_-]{4,160}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


class BatchBoundaryError(ValueError):
    pass


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise BatchBoundaryError(f"Invalid {label}")
    return value


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS customer_intake_batches (
      batch_id TEXT PRIMARY KEY, source_drive_id TEXT NOT NULL,
      source_folder_id TEXT NOT NULL, source_root_id TEXT NOT NULL,
      member_id TEXT NOT NULL DEFAULT '', engagement_id TEXT NOT NULL DEFAULT '',
      destination_drive_id TEXT NOT NULL DEFAULT '', destination_folder_id TEXT NOT NULL DEFAULT '',
      state TEXT NOT NULL DEFAULT 'Unassigned', assigned_by TEXT NOT NULL DEFAULT '',
      assigned_at INTEGER NOT NULL DEFAULT 0, inventory_checkpoint TEXT NOT NULL DEFAULT '',
      inventory_sealed_at INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
      UNIQUE(source_drive_id, source_folder_id)
    );
    CREATE TABLE IF NOT EXISTS customer_intake_items (
      batch_id TEXT NOT NULL, source_item_id TEXT NOT NULL, source_etag TEXT NOT NULL,
      relative_path TEXT NOT NULL, size_bytes INTEGER NOT NULL,
      source_sha256 TEXT NOT NULL DEFAULT '', status TEXT NOT NULL DEFAULT 'Discovered',
      reason TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL,
      PRIMARY KEY(batch_id, source_item_id),
      FOREIGN KEY(batch_id) REFERENCES customer_intake_batches(batch_id)
    );
    CREATE INDEX IF NOT EXISTS idx_customer_batch_items
      ON customer_intake_items(batch_id,status,updated_at);
    """)


def register_batch(conn, *, source_drive_id, source_root_id, source_folder_id,
                   verify_folder, now=None):
    """Register one direct child of the dedicated customer staging root.

    verify_folder(drive, folder, root) must read Graph's live parent and reject
    shortcuts, files, and aliases. No ownership is inferred from upload order.
    """
    drive = _identifier(source_drive_id, "source drive")
    root = _identifier(source_root_id, "staging root")
    folder = _identifier(source_folder_id, "batch folder")
    if folder == root or not verify_folder(drive, folder, root):
        raise BatchBoundaryError("Batch folder is not a verified staging child")
    row = conn.execute(
        "SELECT batch_id,source_root_id FROM customer_intake_batches "
        "WHERE source_drive_id=? AND source_folder_id=?", (drive, folder)
    ).fetchone()
    if row:
        if row["source_root_id"] != root:
            raise BatchBoundaryError("Existing batch has a different source root")
        return row["batch_id"]
    batch_id = "BATCH-" + uuid.uuid4().hex.upper()
    conn.execute(
        "INSERT INTO customer_intake_batches "
        "(batch_id,source_drive_id,source_folder_id,source_root_id,created_at) "
        "VALUES(?,?,?,?,?)", (batch_id,drive,folder,root,int(now or time.time()))
    )
    conn.commit()
    return batch_id


def record_item(conn, batch_id, *, source_item_id, source_etag, relative_path,
                size_bytes, verify_ancestry, now=None):
    """Checkpoint a discovered source without treating it as enterprise knowledge."""
    batch = conn.execute(
        "SELECT * FROM customer_intake_batches WHERE batch_id=?", (batch_id,)
    ).fetchone()
    if not batch or batch["state"] not in ("Unassigned", "Assigned"):
        raise BatchBoundaryError("Batch inventory is sealed or absent")
    item = _identifier(source_item_id, "source item")
    if not isinstance(source_etag, str) or not 1 <= len(source_etag) <= 512:
        raise BatchBoundaryError("Source version is required")
    if (not isinstance(relative_path, str) or not relative_path
            or len(relative_path) > 4096 or relative_path.startswith("/")
            or any(part in ("", ".", "..") for part in relative_path.split("/"))):
        raise BatchBoundaryError("Unsafe relative path")
    if not isinstance(size_bytes, int) or size_bytes < 0:
        raise BatchBoundaryError("Invalid source size")
    if not verify_ancestry(batch["source_drive_id"], item,
                           batch["source_folder_id"]):
        raise BatchBoundaryError("Source is outside its batch folder")
    prior = conn.execute(
        "SELECT source_etag FROM customer_intake_items "
        "WHERE batch_id=? AND source_item_id=?", (batch_id,item)
    ).fetchone()
    if prior and prior["source_etag"] != source_etag:
        # A changed version needs a fresh hash and cannot retain release state.
        conn.execute("UPDATE customer_intake_items SET source_etag=?,relative_path=?,"
                     "size_bytes=?,source_sha256='',status='Discovered',reason='',updated_at=? "
                     "WHERE batch_id=? AND source_item_id=?",
                     (source_etag,relative_path,size_bytes,int(now or time.time()),batch_id,item))
    elif prior:
        conn.execute("UPDATE customer_intake_items SET relative_path=?,size_bytes=?,"
                     "updated_at=? WHERE batch_id=? AND source_item_id=?",
                     (relative_path,size_bytes,int(now or time.time()),batch_id,item))
    else:
        conn.execute("INSERT INTO customer_intake_items "
                     "(batch_id,source_item_id,source_etag,relative_path,size_bytes,updated_at) "
                     "VALUES(?,?,?,?,?,?)",
                     (batch_id,item,source_etag,relative_path,size_bytes,int(now or time.time())))
    conn.commit()


def bind_hash(conn, batch_id, source_item_id, source_etag, source_sha256, *, now=None):
    """Bind a downloaded version; the caller must compute SHA-256 from exact bytes."""
    if not isinstance(source_sha256, str) or not _SHA.fullmatch(source_sha256):
        raise BatchBoundaryError("Invalid source SHA-256")
    prior = conn.execute("SELECT source_sha256 FROM customer_intake_items WHERE "
                         "batch_id=? AND source_item_id=? AND source_etag=?",
                         (batch_id,source_item_id,source_etag)).fetchone()
    if prior and prior["source_sha256"] and prior["source_sha256"] != source_sha256:
        raise BatchBoundaryError("Source version has conflicting content hashes")
    changed = conn.execute("UPDATE customer_intake_items SET source_sha256=?,"
                           "status='Captured',updated_at=? WHERE batch_id=? "
                           "AND source_item_id=? AND source_etag=? AND status IN "
                           "('Discovered','Captured')",
                           (source_sha256,int(now or time.time()),batch_id,
                            source_item_id,source_etag)).rowcount
    conn.commit()
    if changed != 1:
        raise BatchBoundaryError("Source version changed before hash binding")


def assign_batch(conn, batch_id, *, member_id, engagement_id,
                 destination_drive_id, destination_folder_id, actor,
                 verify_route, now=None):
    """Assign once, using an authorized member/engagement and destination lookup.

    verify_route is an authority check against live membership, engagement,
    destination, and access policy; a supplied folder name is not authority.
    """
    member = _identifier(member_id, "member")
    engagement = _identifier(engagement_id, "engagement")
    drive = _identifier(destination_drive_id, "destination drive")
    folder = _identifier(destination_folder_id, "destination folder")
    operator = _identifier(actor, "assigning actor")
    batch = conn.execute("SELECT * FROM customer_intake_batches WHERE batch_id=?",
                         (batch_id,)).fetchone()
    if not batch or batch["state"] != "Unassigned":
        raise BatchBoundaryError("Only an unassigned batch can be assigned")
    if not verify_route(member,engagement,drive,folder,operator):
        raise BatchBoundaryError("Member, engagement, or destination not authorized")
    changed = conn.execute(
        "UPDATE customer_intake_batches SET member_id=?,engagement_id=?,"
        "destination_drive_id=?,destination_folder_id=?,state='Assigned',"
        "assigned_by=?,assigned_at=? WHERE batch_id=? AND state='Unassigned'",
        (member,engagement,drive,folder,operator,int(now or time.time()),batch_id)
    ).rowcount
    conn.commit()
    if changed != 1:
        raise BatchBoundaryError("Batch assignment changed concurrently")


def seal_inventory(conn, batch_id, *, checkpoint, verify_complete_inventory, now=None):
    """Seal only after the folder's durable Graph scan reached its delta link.

    verify_complete_inventory must compare the complete source item set and
    versions to this ledger; a partial scan cannot be released.
    """
    batch = conn.execute("SELECT * FROM customer_intake_batches WHERE batch_id=?",
                         (batch_id,)).fetchone()
    if not batch or batch["state"] != "Assigned":
        raise BatchBoundaryError("A batch assignment is required before sealing")
    if not isinstance(checkpoint, str) or not 1 <= len(checkpoint) <= 8192:
        raise BatchBoundaryError("A completed source checkpoint is required")
    items = conn.execute("SELECT * FROM customer_intake_items WHERE batch_id=?",
                         (batch_id,)).fetchall()
    if (not items or any(item["status"] != "Captured" or
                         not _SHA.fullmatch(item["source_sha256"]) for item in items)
            or not verify_complete_inventory(batch, items, checkpoint)):
        raise BatchBoundaryError("Complete, hash-bound inventory is not verified")
    changed = conn.execute("UPDATE customer_intake_batches SET state='Ready',"
                           "inventory_checkpoint=?,inventory_sealed_at=? "
                           "WHERE batch_id=? AND state='Assigned'",
                           (checkpoint,int(now or time.time()),batch_id)).rowcount
    conn.commit()
    if changed != 1:
        raise BatchBoundaryError("Batch state changed concurrently")


def release_manifest(conn, batch_id, *, verify_route, verify_source,
                     verify_complete_inventory):
    """Return a bound work plan only after repeating live authority checks.

    This does not publish, grant permissions, or mark a batch released.
    The publisher must verify destination bytes, record each outcome, and move
    sources only after exact-hash reconciliation.
    """
    batch = conn.execute("SELECT * FROM customer_intake_batches WHERE batch_id=?",
                         (batch_id,)).fetchone()
    if not batch or batch["state"] != "Ready" or not batch["inventory_checkpoint"]:
        raise BatchBoundaryError("Batch lacks approved assignment or complete inventory")
    if not verify_route(batch["member_id"],batch["engagement_id"],
                        batch["destination_drive_id"],batch["destination_folder_id"],
                        batch["assigned_by"]):
        raise BatchBoundaryError("Destination authority is no longer valid")
    items = conn.execute("SELECT * FROM customer_intake_items WHERE batch_id=? "
                         "ORDER BY relative_path,source_item_id",(batch_id,)).fetchall()
    if not items or any(item["status"] != "Captured" or
                        not _SHA.fullmatch(item["source_sha256"]) for item in items):
        raise BatchBoundaryError("Batch inventory is incomplete")
    if not verify_complete_inventory(batch, items, batch["inventory_checkpoint"]):
        raise BatchBoundaryError("Batch inventory changed since sealing")
    for item in items:
        if not verify_source(batch["source_drive_id"],item["source_item_id"],
                             item["source_etag"],batch["source_folder_id"]):
            raise BatchBoundaryError("Batch source moved or changed")
    return {"batch_id":batch_id,"member_id":batch["member_id"],
            "engagement_id":batch["engagement_id"],
            "destination_drive_id":batch["destination_drive_id"],
            "destination_folder_id":batch["destination_folder_id"],
            "items":[dict(item) for item in items]}
