"""Route five unmatched Knowledge Library sources to governed human review.

The one-time transition changes candidate metadata only. It preserves original
failure rationale and history, adds a fixed audit event, and never downloads or
moves content, changes access, or assigns a Protected Member.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Callable

from database import connect_database


EXPECTED_ROUTE = 5
OPEN_STATUSES = (
    "Pending Review", "Approved for Promotion",
    "Automatic Retry Required", "Destination Verified",
)
EXPECTED_BEFORE = {
    "Pending Review": 8,
    "Approved for Promotion": 3,
    "Automatic Retry Required": 6,
    "Destination Verified": 0,
}
EXPECTED_AFTER = {
    "Pending Review": 13,
    "Approved for Promotion": 3,
    "Automatic Retry Required": 1,
    "Destination Verified": 0,
}
ACTOR = "SalCAPA Governed Source Reconciliation Worker"
EVENT_TYPE = "CandidateRoutedToGovernedSourceReconciliation"
DISPOSITION = "Governed Missing Source Reconciliation Required"
FAILURE_CODES = {
    "Open candidate pre-state changed": "open_prestate_changed",
    "Missing-source candidate pre-state changed": "missing_prestate_changed",
    "Missing-source candidate classification changed": "missing_classification_changed",
    "Missing-source candidate concurrency guard failed": "missing_concurrency_guard",
    "Missing-source transition is incomplete": "transition_incomplete",
    "Missing-source readback is incomplete": "readback_incomplete",
}


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(c.classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"


def _status_counts(conn: Any) -> dict[str, int]:
    marks = ",".join("?" for _ in OPEN_STATUSES)
    rows = conn.execute(
        f"SELECT status,COUNT(*) AS count FROM m365_knowledge_candidates "
        f"WHERE status IN ({marks}) GROUP BY status", OPEN_STATUSES,
    ).fetchall()
    observed = {status: 0 for status in OPEN_STATUSES}
    for row in rows:
        status = str(row["status"] or "")
        if status not in observed:
            raise RuntimeError("Open candidate pre-state changed")
        observed[status] = int(row["count"] or 0)
    return observed


def reconcile(
    conn: Any,
    emit: Callable[[str, str | int], None] | None = None,
) -> dict[str, int]:
    """Atomically route only the five exact unmatched-source obligations."""
    emit = emit or (lambda _key, _value: None)
    if _status_counts(conn) != EXPECTED_BEFORE:
        raise RuntimeError("Open candidate pre-state changed")
    extraction = _json_expression(conn, "extraction,status")
    rationale_family = (
        "CASE WHEN LOWER(c.review_rationale) LIKE '%archive%' "
        "OR LOWER(c.review_rationale) LIKE '%archived source%' "
        "OR LOWER(c.review_rationale) LIKE '%processed intake%' "
        "THEN 'archive' ELSE 'other' END"
    )
    route_sql = (
        "SELECT c.id,c.classification_json FROM m365_knowledge_candidates c "
        "WHERE c.status='Automatic Retry Required' "
        f"AND {extraction}='Complete' AND {rationale_family}='archive' "
        "AND c.destination_drive_id='' AND c.destination_item_id='' "
        "AND c.destination_web_url='' AND c.destination_etag='' "
        "AND c.source_archive_item_id='' AND c.source_archive_web_url='' "
        "AND c.source_archive_etag='' AND c.source_archived_at='' "
        "AND NOT EXISTS (SELECT 1 FROM m365_bulk_items b "
        "WHERE b.drive_id=c.source_drive_id AND b.item_id=c.source_item_id) "
        "AND EXISTS (SELECT 1 FROM m365_knowledge_events e "
        "WHERE e.candidate_id=c.id AND e.event_type='AutomaticPromotionRetryScheduled') "
        "AND NOT EXISTS (SELECT 1 FROM m365_knowledge_events e "
        "WHERE e.candidate_id=c.id AND e.event_type IN "
        "('AutomaticallyPromotedVerifiedAndArchived','PromotedVerifiedAndArchived',?)) "
        "ORDER BY c.id"
    )
    if getattr(conn, "backend", "sqlite") == "postgres":
        route_sql += " FOR UPDATE"
    emit("stage", "missing_prestate_query")
    rows = conn.execute(route_sql, (EVENT_TYPE,)).fetchall()
    emit("pre_missing_count", len(rows))
    if len(rows) != EXPECTED_ROUTE:
        raise RuntimeError("Missing-source candidate pre-state changed")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed = events = 0
    try:
        emit("stage", "metadata_transition")
        for row in rows:
            classification = json.loads(row["classification_json"] or "{}")
            if (classification.get("extraction") or {}).get("status") != "Complete":
                raise RuntimeError("Missing-source candidate classification changed")
            if "source_reconciliation" in classification:
                raise RuntimeError("Missing-source candidate classification changed")
            classification["source_reconciliation"] = {
                "status": "Review Required",
                "disposition": DISPOSITION,
                "successor_match": "None",
                "boundary_files_rechecked": 22_377,
            }
            updated_json = json.dumps(classification, sort_keys=True, separators=(",", ":"))
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET status='Pending Review',"
                "classification_json=? WHERE id=? AND status='Automatic Retry Required' "
                "AND classification_json=?",
                (updated_json, row["id"], row["classification_json"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Missing-source candidate concurrency guard failed")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (row["id"], EVENT_TYPE, ACTOR, json.dumps({
                    "prior_status": "Automatic Retry Required",
                    "status": "Pending Review",
                    "disposition": DISPOSITION,
                    "successor_match": "None",
                    "boundary_files_rechecked": 22_377,
                }, sort_keys=True), timestamp),
            )
            changed += 1
            events += 1
        emit("stage", "aggregate_readback")
        routed = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c "
            "WHERE c.status='Pending Review' AND "
            f"{_json_expression(conn, 'source_reconciliation,status')}='Review Required' "
            f"AND {_json_expression(conn, 'source_reconciliation,disposition')}=?",
            (DISPOSITION,),
        ).fetchone()[0] or 0)
        event_count = int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?", (EVENT_TYPE,),
        ).fetchone()[0] or 0)
        if changed != EXPECTED_ROUTE or events != EXPECTED_ROUTE:
            raise RuntimeError("Missing-source transition is incomplete")
        if (_status_counts(conn) != EXPECTED_AFTER or routed != EXPECTED_ROUTE
                or event_count != EXPECTED_ROUTE):
            raise RuntimeError("Missing-source readback is incomplete")
        conn.commit()
        emit("stage", "committed")
    except Exception:
        conn.rollback()
        raise
    return {
        "missing_sources_routed": changed,
        "audit_events": events,
        "pending_review_total": EXPECTED_AFTER["Pending Review"],
        "automatic_retry_remaining": EXPECTED_AFTER["Automatic Retry Required"],
        "approved_for_promotion_remaining": EXPECTED_AFTER["Approved for Promotion"],
        "open_remaining": sum(EXPECTED_AFTER.values()),
        "content_downloads": 0,
        "source_moves": 0,
        "access_changes": 0,
        "complete": 1,
    }


def main() -> None:
    def emit(key: str, value: str | int) -> None:
        print(f"CANDIDATE_RECONCILE_{key.upper()}={value}", flush=True)

    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live candidate reconciliation requires managed PostgreSQL")
    emit("stage", "database_connect")
    try:
        conn = connect_database()
    except Exception:
        emit("failure", "database_connect_failed")
        emit("complete", 0)
        raise RuntimeError("Candidate reconciliation failed closed") from None
    try:
        result = reconcile(conn, emit)
    except Exception as exc:
        emit("failure", FAILURE_CODES.get(str(exc), "unexpected_database_or_runtime_error"))
        emit("complete", 0)
        raise RuntimeError("Candidate reconciliation failed closed") from None
    finally:
        conn.close()
    for key in sorted(result):
        print(f"CANDIDATE_RECONCILE_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
