"""Bounded, durable retries for extraction from verified archived originals."""

from __future__ import annotations

import json
import time
import uuid
from types import SimpleNamespace


def create_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS m365_bulk_extraction_checks (
      candidate_id BIGINT PRIMARY KEY,
      attempts INTEGER NOT NULL DEFAULT 0,
      next_attempt BIGINT NOT NULL DEFAULT 0,
      lease_owner TEXT NOT NULL DEFAULT '',
      lease_until BIGINT NOT NULL DEFAULT 0,
      checked_at BIGINT NOT NULL DEFAULT 0,
      last_code TEXT NOT NULL DEFAULT ''
    );
    """)


def process_due(conn, *, get_writer, refresh, failure_types, now_iso,
                skip_zip=False, limit=2, clock=None):
    """Retry due archived files; never read a pending source or rewrite its original.

    A durable lease prevents overlapping scheduled jobs from retrying the same
    file. The oldest checked item rotates behind other due items even when its
    decoder fails permanently. Backoff preserves a retry obligation.
    """
    if not 1 <= limit <= 20:
        raise ValueError("Archived extraction retry limit is out of range")
    clock = int(time.time() if clock is None else clock)
    create_tables(conn)
    where_zip = "AND LOWER(c.source_name) NOT LIKE '%.zip'" if skip_zip else ""
    rows = conn.execute(
        "SELECT c.id,c.source_name,c.source_sha256,c.source_archive_item_id,"
        "c.classification_json FROM m365_knowledge_candidates c "
        "LEFT JOIN m365_bulk_extraction_checks r ON r.candidate_id=c.id "
        "WHERE c.status='Ingested and Verified' "
        "AND c.source_archive_item_id<>'' "
        "AND c.classification_json LIKE '%\"status\": \"Automatic Retry Required\"%' "
        "AND COALESCE(r.next_attempt,0)<=? AND COALESCE(r.lease_until,0)<? "
        + where_zip +
        " ORDER BY COALESCE(r.checked_at,0),c.id LIMIT ?",
        (clock, clock, limit),
    ).fetchall()
    completed, retried, retry_codes = 0, 0, set()
    for row in rows:
        classification = json.loads(row["classification_json"] or "{}")
        if classification.get("extraction", {}).get("status") != "Automatic Retry Required":
            continue
        owner = uuid.uuid4().hex
        claimed = conn.execute(
            "INSERT INTO m365_bulk_extraction_checks"
            "(candidate_id,attempts,next_attempt,lease_owner,lease_until,checked_at) "
            "VALUES(?,1,0,?,?,?) ON CONFLICT(candidate_id) DO UPDATE SET "
            "attempts=m365_bulk_extraction_checks.attempts+1,"
            "lease_owner=excluded.lease_owner,lease_until=excluded.lease_until,"
            "checked_at=excluded.checked_at "
            "WHERE m365_bulk_extraction_checks.next_attempt<=? "
            "AND m365_bulk_extraction_checks.lease_until<? RETURNING attempts",
            (row["id"], owner, clock + 300, clock, clock, clock),
        ).fetchone()
        conn.commit()
        if claimed is None:
            continue
        code = ""
        try:
            verified = get_writer().verify_already_archived_source(
                row["source_archive_item_id"], row["source_sha256"],
                include_content=True,
            )
            if verified is None:
                code = "archived_source_outside_verified_folder"
            else:
                document = SimpleNamespace(
                    name=row["source_name"], content=verified["content"],
                    sha256=row["source_sha256"],
                    mime_type=classification.get("citation_metadata", {}).get(
                        "source_mime_type", "application/octet-stream"),
                )
                classification, code = refresh(
                    classification, document, row["source_sha256"]
                )
        except failure_types:
            code = "archived_source_read_unavailable"
        if code:
            retried += 1
            retry_codes.add(code)
            delay = min(86400, 60 * (2 ** min(claimed["attempts"] - 1, 10)))
            conn.execute(
                "UPDATE m365_bulk_extraction_checks SET next_attempt=?,"
                "lease_owner='',lease_until=0,last_code=? "
                "WHERE candidate_id=? AND lease_owner=?",
                (clock + delay, code[:120], row["id"], owner),
            )
            conn.commit()
            continue
        updated = conn.execute(
            "UPDATE m365_knowledge_candidates SET classification_json=? "
            "WHERE id=? AND status='Ingested and Verified' AND source_sha256=?",
            (json.dumps(classification, sort_keys=True), row["id"], row["source_sha256"]),
        )
        if updated.rowcount == 1:
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (row["id"], "AutomaticArchivedExtractionCompleted", "SalCAPA Policy Engine",
                 json.dumps({"source_sha256": row["source_sha256"]}), now_iso()),
            )
            completed += 1
        conn.execute(
            "UPDATE m365_bulk_extraction_checks SET lease_owner='',lease_until=0,"
            "next_attempt=0,last_code='' WHERE candidate_id=? AND lease_owner=?",
            (row["id"], owner),
        )
        conn.commit()
    return {"completed": completed, "retry": retried,
            "codes": sorted(retry_codes)}
