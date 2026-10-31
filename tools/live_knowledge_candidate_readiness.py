"""Read-only aggregate readiness evidence for open Knowledge Library candidates.

The probe emits bounded counts only. It never selects or logs a source ID,
name, path, content, attribution, identity, URL, free-text rationale, or event
detail, and it changes no ledger or Microsoft 365 state.
"""

from __future__ import annotations

import os
from typing import Any

from database import connect_database


EXPECTED_INITIAL_STATUS_COUNTS = {
    "Pending Review": 8,
    "Approved for Promotion": 3,
    "Automatic Retry Required": 6,
    "Destination Verified": 0,
}
EXPECTED_INITIAL_TOTAL = 17
OPEN_STATUSES = tuple(EXPECTED_INITIAL_STATUS_COUNTS)
EXTRACTION_STATUSES = ("Complete", "Review Required", "Retry Paused")
KNOWN_EVENTS = (
    "Captured",
    "AutomaticallyClassified",
    "AutomaticExtractionRetryScheduled",
    "AutomaticPromotionRetryScheduled",
    "AutomaticallyPromotedVerifiedAndArchived",
    "CandidateRoutedToGovernedExtractionReview",
)


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(c.classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"


def _key(value: str) -> str:
    return value.lower().replace(" ", "_")


def collect(
    conn: Any,
    expected_status_counts: dict[str, int] = EXPECTED_INITIAL_STATUS_COUNTS,
) -> dict[str, int]:
    """Collect aggregate evidence and fail closed on scope growth or drift."""
    if tuple(expected_status_counts) != OPEN_STATUSES:
        raise RuntimeError("Open-candidate status boundary changed")
    if expected_status_counts is EXPECTED_INITIAL_STATUS_COUNTS and (
        sum(expected_status_counts.values()) != EXPECTED_INITIAL_TOTAL
    ):
        raise RuntimeError("Open-candidate expectation is invalid")
    expected_total = sum(expected_status_counts.values())

    marks = ",".join("?" for _ in OPEN_STATUSES)
    extraction = _json_expression(conn, "extraction,status")
    rows = conn.execute(
        f"SELECT c.status,{extraction} AS extraction_status,COUNT(*) AS count "
        "FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) GROUP BY c.status,extraction_status",
        OPEN_STATUSES,
    ).fetchall()
    observed = {status: 0 for status in OPEN_STATUSES}
    matrix = {
        f"{_key(status)}_{_key(extraction_status)}": 0
        for status in OPEN_STATUSES for extraction_status in EXTRACTION_STATUSES
    }
    unexpected_extraction = 0
    for row in rows:
        status = str(row["status"] or "")
        extraction_status = str(row["extraction_status"] or "")
        count = int(row["count"] or 0)
        if status not in observed:
            raise RuntimeError("Open-candidate status left the approved boundary")
        observed[status] += count
        if extraction_status not in EXTRACTION_STATUSES:
            unexpected_extraction += count
            continue
        matrix[f"{_key(status)}_{_key(extraction_status)}"] += count
    if any(observed[status] > expected_status_counts[status] for status in OPEN_STATUSES):
        raise RuntimeError("Open-candidate count exceeded its approved boundary")
    if unexpected_extraction:
        raise RuntimeError("Open candidate has an unexpected extraction state")

    metadata = conn.execute(
        "SELECT COUNT(*) AS total,"
        "SUM(CASE WHEN decision='Approved' THEN 1 ELSE 0 END) AS decision_approved,"
        "SUM(CASE WHEN target_folder<>'' THEN 1 ELSE 0 END) AS target_configured,"
        "SUM(CASE WHEN destination_drive_id<>'' OR destination_item_id<>'' "
        "OR destination_web_url<>'' OR destination_etag<>'' THEN 1 ELSE 0 END) AS destination_any,"
        "SUM(CASE WHEN destination_drive_id<>'' AND destination_item_id<>'' "
        "AND destination_web_url<>'' AND destination_etag<>'' THEN 1 ELSE 0 END) AS destination_complete,"
        "SUM(CASE WHEN source_archive_item_id<>'' OR source_archive_web_url<>'' "
        "OR source_archive_etag<>'' OR source_archived_at<>'' THEN 1 ELSE 0 END) AS archive_any,"
        "SUM(CASE WHEN source_archive_item_id<>'' AND source_archive_web_url<>'' "
        "AND source_archive_etag<>'' AND source_archived_at<>'' THEN 1 ELSE 0 END) AS archive_complete,"
        "SUM(CASE WHEN review_rationale='' THEN 1 ELSE 0 END) AS rationale_blank,"
        "SUM(CASE WHEN LOWER(review_rationale) LIKE '%automatically processed under%' THEN 1 ELSE 0 END) AS rationale_policy,"
        "SUM(CASE WHEN LOWER(review_rationale) LIKE '%destination%' OR LOWER(review_rationale) LIKE '%knowledge folder%' THEN 1 ELSE 0 END) AS rationale_destination,"
        "SUM(CASE WHEN LOWER(review_rationale) LIKE '%upload%' THEN 1 ELSE 0 END) AS rationale_upload,"
        "SUM(CASE WHEN LOWER(review_rationale) LIKE '%archive%' OR LOWER(review_rationale) LIKE '%archived source%' THEN 1 ELSE 0 END) AS rationale_archive,"
        "SUM(CASE WHEN LOWER(review_rationale) LIKE '%token%' OR LOWER(review_rationale) LIKE '%identity%' THEN 1 ELSE 0 END) AS rationale_identity "
        "FROM m365_knowledge_candidates "
        f"WHERE status IN ({marks})",
        OPEN_STATUSES,
    ).fetchone()
    total = sum(observed.values())
    if int(metadata["total"] or 0) != total:
        raise RuntimeError("Open-candidate metadata total changed")
    categorized_rationale = sum(int(metadata[key] or 0) for key in (
        "rationale_blank", "rationale_policy", "rationale_destination",
        "rationale_upload", "rationale_archive", "rationale_identity",
    ))
    # Pattern categories are intentionally fixed and may overlap. The bounded
    # remainder is therefore only safe when no known category matched.
    rationale_other = int(conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE "
        f"status IN ({marks}) AND review_rationale<>'' "
        "AND LOWER(review_rationale) NOT LIKE '%automatically processed under%' "
        "AND LOWER(review_rationale) NOT LIKE '%destination%' "
        "AND LOWER(review_rationale) NOT LIKE '%knowledge folder%' "
        "AND LOWER(review_rationale) NOT LIKE '%upload%' "
        "AND LOWER(review_rationale) NOT LIKE '%archive%' "
        "AND LOWER(review_rationale) NOT LIKE '%archived source%' "
        "AND LOWER(review_rationale) NOT LIKE '%token%' "
        "AND LOWER(review_rationale) NOT LIKE '%identity%'",
        OPEN_STATUSES,
    ).fetchone()[0] or 0)

    events = conn.execute(
        "SELECT e.event_type,COUNT(*) AS count FROM m365_knowledge_events e "
        "JOIN m365_knowledge_candidates c ON c.id=e.candidate_id "
        f"WHERE c.status IN ({marks}) GROUP BY e.event_type",
        OPEN_STATUSES,
    ).fetchall()
    event_counts = {name: 0 for name in KNOWN_EVENTS}
    event_other = 0
    for row in events:
        name = str(row["event_type"] or "")
        count = int(row["count"] or 0)
        if name in event_counts:
            event_counts[name] += count
        else:
            event_other += count

    result = {
        "open_remaining": total,
        "resolved_since_checkpoint": expected_total - total,
        "unexpected_extraction": unexpected_extraction,
        "decision_approved": int(metadata["decision_approved"] or 0),
        "decision_not_approved": total - int(metadata["decision_approved"] or 0),
        "target_configured": int(metadata["target_configured"] or 0),
        "target_missing": total - int(metadata["target_configured"] or 0),
        "destination_any": int(metadata["destination_any"] or 0),
        "destination_complete": int(metadata["destination_complete"] or 0),
        "archive_any": int(metadata["archive_any"] or 0),
        "archive_complete": int(metadata["archive_complete"] or 0),
        "rationale_blank": int(metadata["rationale_blank"] or 0),
        "rationale_policy": int(metadata["rationale_policy"] or 0),
        "rationale_destination": int(metadata["rationale_destination"] or 0),
        "rationale_upload": int(metadata["rationale_upload"] or 0),
        "rationale_archive": int(metadata["rationale_archive"] or 0),
        "rationale_identity": int(metadata["rationale_identity"] or 0),
        "rationale_other": rationale_other,
        "known_rationale_matches": categorized_rationale,
        "event_other": event_other,
        "content_downloads": 0,
        "rows_changed": 0,
    }
    result.update({f"status_{_key(status)}": count for status, count in observed.items()})
    result.update({f"matrix_{key}": count for key, count in matrix.items()})
    result.update({f"event_{_key(name)}": count for name, count in event_counts.items()})
    return result


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live open-candidate probe requires managed PostgreSQL")
    conn = connect_database()
    try:
        result = collect(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"CANDIDATE_READY_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
