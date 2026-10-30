"""Reconcile bounded stale and review-blocked Knowledge Library candidates.

The one-time transition changes ledger metadata only. It never downloads or
moves source content, changes access, or assigns a Protected Member.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any

from database import connect_database


EXPECTED_STALE_PROMOTED = 1
EXPECTED_REVIEW_BLOCKED = 8
OPEN_STATUSES = ("Pending Review", "Approved for Promotion", "Automatic Retry Required", "Destination Verified")
ACTOR = "SalCAPA Governed Candidate Reconciliation Worker"


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(c.classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"


def reconcile(conn: Any) -> dict[str, int]:
    """Atomically reconcile the exact verified metadata states."""
    marks = ",".join("?" for _ in OPEN_STATUSES)
    extraction_status = _json_expression(conn, "extraction,status")
    extraction_disposition = _json_expression(conn, "extraction,disposition")
    stale_sql = (
        "SELECT c.id,c.status,c.classification_json FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) AND {extraction_status}='Complete' "
        "AND c.destination_drive_id<>'' AND c.destination_item_id<>'' "
        "AND c.destination_web_url<>'' AND c.destination_etag<>'' "
        "AND c.source_archive_item_id<>'' AND c.source_archive_web_url<>'' "
        "AND c.source_archive_etag<>'' AND c.source_archived_at<>'' "
        "AND EXISTS (SELECT 1 FROM m365_knowledge_events e WHERE e.candidate_id=c.id "
        "AND e.event_type='AutomaticallyPromotedVerifiedAndArchived') ORDER BY c.id"
    )
    review_sql = (
        "SELECT c.id,c.status,c.classification_json FROM m365_knowledge_candidates c "
        "WHERE c.status='Automatic Retry Required' "
        f"AND {extraction_status}='Review Required' "
        f"AND {extraction_disposition}='Governed Extraction Review Required' ORDER BY c.id"
    )
    if getattr(conn, "backend", "sqlite") == "postgres":
        stale_sql += " FOR UPDATE"
        review_sql += " FOR UPDATE"
    stale = conn.execute(stale_sql, OPEN_STATUSES).fetchall()
    review = conn.execute(review_sql).fetchall()
    if len(stale) != EXPECTED_STALE_PROMOTED:
        raise RuntimeError("Stale promoted-candidate pre-state changed")
    if len(review) != EXPECTED_REVIEW_BLOCKED:
        raise RuntimeError("Review-blocked candidate pre-state changed")
    if {int(row["id"]) for row in stale} & {int(row["id"]) for row in review}:
        raise RuntimeError("Candidate reconciliation sets overlap")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    stale_changed = review_changed = events = 0
    try:
        for row in stale:
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Ingested and Verified' "
                "WHERE id=? AND status=? AND classification_json=?",
                (row["id"], row["status"], row["classification_json"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Stale promoted-candidate concurrency guard failed")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (row["id"], "CandidateStatusReconciledFromVerifiedPromotion", ACTOR,
                 json.dumps({"prior_status": row["status"], "status": "Ingested and Verified",
                             "basis": "complete_destination_archive_and_promotion_event"}, sort_keys=True),
                 timestamp),
            )
            stale_changed += 1
            events += 1
        for row in review:
            classification = json.loads(row["classification_json"] or "{}")
            extraction = classification.get("extraction") or {}
            if (extraction.get("status") != "Review Required" or
                    extraction.get("disposition") != "Governed Extraction Review Required"):
                raise RuntimeError("Review-blocked candidate classification changed")
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Pending Review' "
                "WHERE id=? AND status='Automatic Retry Required' AND classification_json=?",
                (row["id"], row["classification_json"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Review-blocked candidate concurrency guard failed")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (row["id"], "CandidateRoutedToGovernedExtractionReview", ACTOR,
                 json.dumps({"prior_status": "Automatic Retry Required", "status": "Pending Review",
                             "disposition": "Governed Extraction Review Required"}, sort_keys=True),
                 timestamp),
            )
            review_changed += 1
            events += 1
        open_remaining = int(conn.execute(
            f"SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status IN ({marks})",
            OPEN_STATUSES,
        ).fetchone()[0] or 0)
        pending_review = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c WHERE c.status='Pending Review' "
            f"AND {extraction_status}='Review Required' "
            f"AND {extraction_disposition}='Governed Extraction Review Required'"
        ).fetchone()[0] or 0)
        if stale_changed != 1 or review_changed != 8 or events != 9:
            raise RuntimeError("Candidate reconciliation transition is incomplete")
        if open_remaining != 16 or pending_review != 8:
            raise RuntimeError("Candidate reconciliation readback is incomplete")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {
        "stale_promoted_reconciled": stale_changed,
        "review_blocked_routed": review_changed,
        "audit_events": events,
        "open_remaining": open_remaining,
        "pending_governed_review": pending_review,
        "content_downloads": 0,
        "source_moves": 0,
        "complete": 1,
    }


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live candidate reconciliation requires managed PostgreSQL")
    conn = connect_database()
    try:
        result = reconcile(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"CANDIDATE_RECONCILE_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
