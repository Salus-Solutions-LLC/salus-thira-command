"""Read-only aggregate readiness evidence for open Knowledge Library candidates.

The probe emits bounded counts only. It never selects or logs a source ID,
name, path, content, attribution, identity, URL, free-text rationale, or event
detail, and it changes no ledger or Microsoft 365 state.
"""

from __future__ import annotations

import os
import time
from typing import Any

from database import connect_database


EXPECTED_INITIAL_STATUS_COUNTS = {
    "Pending Review": 8,
    "Approved for Promotion": 3,
    "Automatic Retry Required": 6,
    "Destination Verified": 0,
}
EXPECTED_INITIAL_TOTAL = 17
EXPECTED_PROMOTION_SCOPE_COUNTS = {
    "Approved for Promotion": 3,
    "Automatic Retry Required": 6,
}
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


def _evidence_state(fields: tuple[str, ...]) -> str:
    any_evidence = " OR ".join(f"c.{field}<>''" for field in fields)
    complete_evidence = " AND ".join(f"c.{field}<>''" for field in fields)
    return (
        f"CASE WHEN {complete_evidence} THEN 'complete' "
        f"WHEN {any_evidence} THEN 'partial' ELSE 'none' END"
    )


def _promotion_fingerprints(
    conn: Any,
    expected_counts: dict[str, int],
) -> dict[str, int]:
    """Group the fixed nine-candidate scope without selecting an item identity."""
    statuses = tuple(EXPECTED_PROMOTION_SCOPE_COUNTS)
    if tuple(expected_counts) != statuses:
        raise RuntimeError("Promotion-diagnostic status boundary changed")
    extraction = _json_expression(conn, "extraction,status")
    destination_state = _evidence_state((
        "destination_drive_id", "destination_item_id",
        "destination_web_url", "destination_etag",
    ))
    archive_state = _evidence_state((
        "source_archive_item_id", "source_archive_web_url",
        "source_archive_etag", "source_archived_at",
    ))
    # This is deliberately exclusive, fixed and coarse. The query never
    # returns the rationale itself, only one allowlisted family per candidate.
    rationale_family = (
        "CASE WHEN TRIM(c.review_rationale)='' THEN 'blank' "
        "WHEN LOWER(c.review_rationale) LIKE '%automatically processed under%' THEN 'policy' "
        "WHEN LOWER(c.review_rationale) LIKE '%upload%' THEN 'upload' "
        "WHEN LOWER(c.review_rationale) LIKE '%archive%' "
        "OR LOWER(c.review_rationale) LIKE '%archived source%' "
        "OR LOWER(c.review_rationale) LIKE '%processed intake%' THEN 'archive' "
        "WHEN LOWER(c.review_rationale) LIKE '%destination%' "
        "OR LOWER(c.review_rationale) LIKE '%knowledge folder%' THEN 'destination' "
        "WHEN LOWER(c.review_rationale) LIKE '%token%' "
        "OR LOWER(c.review_rationale) LIKE '%identity%' THEN 'identity' "
        "ELSE 'other' END"
    )
    promotion_event = (
        "CASE WHEN EXISTS (SELECT 1 FROM m365_knowledge_events pe "
        "WHERE pe.candidate_id=c.id AND pe.event_type IN "
        "('AutomaticallyPromotedVerifiedAndArchived','PromotedVerifiedAndArchived')) "
        "THEN 'present' ELSE 'absent' END"
    )
    retry_event = (
        "CASE WHEN EXISTS (SELECT 1 FROM m365_knowledge_events re "
        "WHERE re.candidate_id=c.id "
        "AND re.event_type='AutomaticPromotionRetryScheduled') "
        "THEN 'present' ELSE 'absent' END"
    )
    marks = ",".join("?" for _ in statuses)
    rows = conn.execute(
        "SELECT status,destination_state,archive_state,rationale_family,"
        "promotion_event,retry_event,COUNT(*) AS count FROM ("
        f"SELECT c.status AS status,{destination_state} AS destination_state,"
        f"{archive_state} AS archive_state,{rationale_family} AS rationale_family,"
        f"{promotion_event} AS promotion_event,{retry_event} AS retry_event "
        "FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) AND {extraction}='Complete'"
        ") scoped GROUP BY status,destination_state,archive_state,rationale_family,"
        "promotion_event,retry_event",
        statuses,
    ).fetchall()
    allowed_evidence = {"none", "partial", "complete"}
    allowed_rationale = {
        "blank", "policy", "upload", "archive", "destination", "identity", "other",
    }
    allowed_event = {"absent", "present"}
    observed = {status: 0 for status in statuses}
    result: dict[str, int] = {}
    for row in rows:
        status = str(row["status"] or "")
        destination = str(row["destination_state"] or "")
        archive = str(row["archive_state"] or "")
        rationale = str(row["rationale_family"] or "")
        promoted = str(row["promotion_event"] or "")
        retry = str(row["retry_event"] or "")
        count = int(row["count"] or 0)
        if (
            status not in observed or destination not in allowed_evidence
            or archive not in allowed_evidence or rationale not in allowed_rationale
            or promoted not in allowed_event or retry not in allowed_event
        ):
            raise RuntimeError("Promotion-diagnostic category left the fixed boundary")
        observed[status] += count
        fingerprint = "_".join((
            "promotion_fingerprint", _key(status),
            f"destination_{destination}", f"archive_{archive}",
            f"rationale_{rationale}", f"promoted_{promoted}", f"retry_{retry}",
        ))
        result[fingerprint] = count
    if observed != expected_counts:
        raise RuntimeError("Promotion-diagnostic exact candidate scope changed")
    result["promotion_scope_total"] = sum(observed.values())
    result["promotion_scope_fingerprint_groups"] = len(rows)
    result.update({
        f"promotion_scope_status_{_key(status)}": count
        for status, count in observed.items()
    })
    return result


def _work_fingerprints(
    conn: Any,
    expected_counts: dict[str, int],
    clock: int,
) -> dict[str, int]:
    """Correlate the fixed nine candidates to bounded durable-work categories."""
    statuses = tuple(EXPECTED_PROMOTION_SCOPE_COUNTS)
    if tuple(expected_counts) != statuses:
        raise RuntimeError("Work-diagnostic status boundary changed")
    extraction = _json_expression(conn, "extraction,status")
    match = (
        "b.drive_id=c.source_drive_id AND b.item_id=c.source_item_id"
    )
    match_count = f"(SELECT COUNT(*) FROM m365_bulk_items b WHERE {match})"
    work_value = lambda column: (
        f"(SELECT b.{column} FROM m365_bulk_items b WHERE {match} LIMIT 1)"
    )
    work_status = work_value("status")
    work_reason = work_value("reason")
    work_attempts = work_value("attempts")
    work_next_attempt = work_value("next_attempt")
    work_lease_until = work_value("lease_until")
    failure_family = (
        "CASE WHEN TRIM(c.review_rationale)='' THEN 'blank' "
        "WHEN LOWER(c.review_rationale) LIKE '%automatically processed under%' THEN 'policy' "
        "WHEN LOWER(c.review_rationale)='approved knowledge file could not be written' "
        "THEN 'destination_write_denied' "
        "WHEN LOWER(c.review_rationale)='knowledge destination could not be read' "
        "THEN 'destination_read_denied' "
        "WHEN LOWER(c.review_rationale)='approved knowledge folder was not uniquely resolved' "
        "THEN 'destination_folder_unresolved' "
        "WHEN LOWER(c.review_rationale)='knowledge destination verification failed' "
        "THEN 'destination_verification_failed' "
        "WHEN LOWER(c.review_rationale) LIKE "
        "'verified intake source could not be archived (http 423)%' THEN 'archive_locked' "
        "WHEN LOWER(c.review_rationale) LIKE "
        "'verified intake source could not be archived (http %' THEN 'archive_http_other' "
        "WHEN LOWER(c.review_rationale) LIKE '%archive%' "
        "OR LOWER(c.review_rationale) LIKE '%archived source%' "
        "OR LOWER(c.review_rationale) LIKE '%processed intake%' THEN 'archive_other' "
        "WHEN LOWER(c.review_rationale) LIKE '%upload%' THEN 'upload' "
        "WHEN LOWER(c.review_rationale) LIKE '%destination%' "
        "OR LOWER(c.review_rationale) LIKE '%knowledge folder%' THEN 'destination_other' "
        "WHEN LOWER(c.review_rationale) LIKE '%token%' "
        "OR LOWER(c.review_rationale) LIKE '%identity%' THEN 'identity' "
        "ELSE 'other' END"
    )
    work_state = (
        f"CASE WHEN {match_count}=0 THEN 'missing' "
        f"WHEN {match_count}>1 THEN 'multiple' "
        f"WHEN {work_status}='Pending' THEN 'pending' "
        f"WHEN {work_status}='Retry' THEN 'retry' "
        f"WHEN {work_status}='Working' THEN 'working' "
        f"WHEN {work_status}='Done' THEN 'done' "
        f"WHEN {work_status}='Oversize' THEN 'oversize' "
        f"WHEN {work_status}='Assignment Required' THEN 'assignment_required' "
        f"WHEN {work_status}='Removed' THEN 'removed' ELSE 'other' END"
    )
    reason_family = (
        f"CASE WHEN {match_count}=0 THEN 'missing' WHEN {match_count}>1 THEN 'multiple' "
        f"WHEN COALESCE({work_reason},'')='' THEN 'blank' "
        f"WHEN {work_reason}='promotion_retry_required' THEN 'promotion_retry' "
        f"WHEN {work_reason}='source_changed_during_scan' THEN 'source_changed' "
        f"WHEN {work_reason}='enterprise_route_assignment_required' THEN 'route_assignment' "
        f"WHEN {work_reason}='file_size_limit' THEN 'size_limit' ELSE 'other' END"
    )
    attempt_bucket = (
        f"CASE WHEN {match_count}=0 THEN 'missing' WHEN {match_count}>1 THEN 'multiple' "
        f"WHEN COALESCE({work_attempts},0)=0 THEN 'zero' "
        f"WHEN {work_attempts} BETWEEN 1 AND 2 THEN 'one_two' "
        f"WHEN {work_attempts} BETWEEN 3 AND 5 THEN 'three_five' "
        "ELSE 'six_plus' END"
    )
    schedule_state = (
        f"CASE WHEN {match_count}=0 THEN 'missing' WHEN {match_count}>1 THEN 'multiple' "
        f"WHEN {work_status}='Retry' AND {work_next_attempt}<={int(clock)} THEN 'retry_due' "
        f"WHEN {work_status}='Retry' THEN 'retry_backoff' "
        f"WHEN {work_status}='Working' AND {work_lease_until}>{int(clock)} THEN 'working_active' "
        f"WHEN {work_status}='Working' THEN 'working_expired' ELSE 'not_scheduled' END"
    )
    marks = ",".join("?" for _ in statuses)
    rows = conn.execute(
        "SELECT status,failure_family,work_state,reason_family,attempt_bucket,"
        "schedule_state,COUNT(*) AS count FROM ("
        f"SELECT c.status AS status,{failure_family} AS failure_family,"
        f"{work_state} AS work_state,{reason_family} AS reason_family,"
        f"{attempt_bucket} AS attempt_bucket,{schedule_state} AS schedule_state "
        "FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) AND {extraction}='Complete'"
        ") scoped GROUP BY status,failure_family,work_state,reason_family,"
        "attempt_bucket,schedule_state",
        statuses,
    ).fetchall()
    allowed_failure = {
        "blank", "policy", "destination_write_denied", "destination_read_denied",
        "destination_folder_unresolved", "destination_verification_failed",
        "archive_locked", "archive_http_other", "archive_other", "upload",
        "destination_other", "identity", "other",
    }
    allowed_work = {
        "missing", "multiple", "pending", "retry", "working", "done", "oversize",
        "assignment_required", "removed", "other",
    }
    allowed_reason = {
        "missing", "multiple", "blank", "promotion_retry", "source_changed",
        "route_assignment", "size_limit", "other",
    }
    allowed_attempt = {"missing", "multiple", "zero", "one_two", "three_five", "six_plus"}
    allowed_schedule = {
        "missing", "multiple", "retry_due", "retry_backoff", "working_active",
        "working_expired", "not_scheduled",
    }
    observed = {status: 0 for status in statuses}
    result: dict[str, int] = {}
    for row in rows:
        status = str(row["status"] or "")
        failure = str(row["failure_family"] or "")
        work = str(row["work_state"] or "")
        reason = str(row["reason_family"] or "")
        attempt = str(row["attempt_bucket"] or "")
        schedule = str(row["schedule_state"] or "")
        count = int(row["count"] or 0)
        if (
            status not in observed or failure not in allowed_failure
            or work not in allowed_work or reason not in allowed_reason
            or attempt not in allowed_attempt or schedule not in allowed_schedule
        ):
            raise RuntimeError("Work-diagnostic category left the fixed boundary")
        observed[status] += count
        key = "_".join((
            "work_fingerprint", _key(status), f"failure_{failure}", f"work_{work}",
            f"reason_{reason}", f"attempts_{attempt}", f"schedule_{schedule}",
        ))
        result[key] = count
    if observed != expected_counts:
        raise RuntimeError("Work-diagnostic exact candidate scope changed")
    result["work_scope_total"] = sum(observed.values())
    result["work_scope_fingerprint_groups"] = len(rows)
    return result


def collect(
    conn: Any,
    expected_status_counts: dict[str, int] = EXPECTED_INITIAL_STATUS_COUNTS,
    expected_promotion_counts: dict[str, int] = EXPECTED_PROMOTION_SCOPE_COUNTS,
    clock: int | None = None,
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
    result.update(_promotion_fingerprints(conn, expected_promotion_counts))
    result.update(_work_fingerprints(
        conn, expected_promotion_counts, int(time.time() if clock is None else clock)
    ))
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
