"""Read-only aggregate readiness evidence for open Knowledge Library candidates.

The protected entrypoint reads managed PostgreSQL aggregate categories only.
It makes no Microsoft Graph request, emits no identifier, name, path, content,
attribution, identity, URL, free-text rationale, event detail, or raw work
reason, and changes no governed state.
"""

from __future__ import annotations

import os
import re
import time
import hashlib
from collections import deque
from typing import Any
from urllib.parse import quote, urlparse

from database import connect_database


GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
_SOURCE_ID = re.compile(r"^[A-Za-z0-9_!.-]{8,256}$")


EXPECTED_INITIAL_STATUS_COUNTS = {
    "Pending Review": 13,
    "Approved for Promotion": 0,
    "Automatic Retry Required": 0,
    "Destination Verified": 0,
}
EXPECTED_INITIAL_TOTAL = 13
EXPECTED_PROMOTION_SCOPE_COUNTS = {
    "Approved for Promotion": 0,
    "Automatic Retry Required": 0,
}
EXPECTED_PENDING_REVIEW_COUNTS = {
    "extraction_review": 8,
    "source_reconciliation": 5,
}
EXPECTED_SOURCE_STATE_COUNTS: dict[tuple[str, str], int] = {}
EXPECTED_EXTRACTION_REVIEWS = 8
EXPECTED_SOURCE_RECONCILIATIONS = 5
SOURCE_RECONCILIATION_DISPOSITION = "Governed Missing Source Reconciliation Required"
EXTRACTION_REVIEW_DISPOSITION = "Governed Extraction Review Required"
EXPECTED_PROCESSED_EVIDENCE_SCOPE = 0
SOURCE_AREA_KEYS = {
    "20 Ready for Intake Review": "ready_for_intake_review",
    "30 Exceptions and Manual Review": "exceptions_and_manual_review",
    "40 Customer Batch Staging - Unassigned": "customer_batch_staging_unassigned",
    "90 Migration Hold": "migration_hold",
    "90 Processed Intake": "processed_intake",
    "Does Not Upload": "does_not_upload",
}
EXPECTED_BOUNDARY_FILES = 22_377
MAX_BOUNDARY_ITEMS = 50_000
MAX_BOUNDARY_FOLDERS = 5_000
MAX_BOUNDARY_PAGES = 1_000
OPEN_STATUSES = tuple(EXPECTED_INITIAL_STATUS_COUNTS)
EXTRACTION_STATUSES = ("Complete", "Review Required", "Retry Paused")
KNOWN_EVENTS = (
    "Captured",
    "AutomaticallyClassified",
    "AutomaticExtractionRetryScheduled",
    "AutomaticPromotionRetryScheduled",
    "AutomaticallyPromotedVerifiedAndArchived",
    "CandidateRoutedToGovernedExtractionReview",
    "CandidateRoutedToGovernedSourceReconciliation",
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


def _pending_review_fingerprints(
    conn: Any,
    expected_counts: dict[str, int] = EXPECTED_PENDING_REVIEW_COUNTS,
) -> dict[str, int]:
    """Group the exact 13-item review scope without selecting item identity."""
    if expected_counts != EXPECTED_PENDING_REVIEW_COUNTS:
        raise RuntimeError("Pending-review expectation changed")
    extraction_status = _json_expression(conn, "extraction,status")
    extraction_disposition = _json_expression(conn, "extraction,disposition")
    extraction_retry = _json_expression(conn, "extraction,retry_eligible")
    extraction_code = _json_expression(conn, "extraction,failure_code")
    reconciliation_status = _json_expression(conn, "source_reconciliation,status")
    reconciliation_disposition = _json_expression(
        conn, "source_reconciliation,disposition"
    )
    reconciliation_match = _json_expression(conn, "source_reconciliation,successor_match")
    reconciliation_boundary = _json_expression(
        conn, "source_reconciliation,boundary_files_rechecked"
    )
    extraction_event = (
        "EXISTS (SELECT 1 FROM m365_knowledge_events ee WHERE ee.candidate_id=c.id "
        "AND ee.event_type='CandidateRoutedToGovernedExtractionReview')"
    )
    reconciliation_event = (
        "EXISTS (SELECT 1 FROM m365_knowledge_events se WHERE se.candidate_id=c.id "
        "AND se.event_type='CandidateRoutedToGovernedSourceReconciliation')"
    )
    review_type = (
        "CASE WHEN "
        f"{extraction_status}='Review Required' AND "
        f"{extraction_disposition}='{EXTRACTION_REVIEW_DISPOSITION}' AND "
        f"CAST({extraction_retry} AS TEXT) IN ('false','0') AND {extraction_event} AND "
        f"{reconciliation_status}='' THEN 'extraction_review' "
        "WHEN "
        f"{extraction_status}='Complete' AND "
        f"{reconciliation_status}='Review Required' AND "
        f"{reconciliation_disposition}='{SOURCE_RECONCILIATION_DISPOSITION}' AND "
        f"{reconciliation_match}='None' AND "
        f"CAST({reconciliation_boundary} AS TEXT)='22377' AND {reconciliation_event} "
        "THEN 'source_reconciliation' ELSE 'other' END"
    )
    normalized_extraction = (
        f"CASE WHEN {extraction_status}='Review Required' THEN 'review_required' "
        f"WHEN {extraction_status}='Complete' THEN 'complete' ELSE 'other' END"
    )
    failure_family = (
        f"CASE WHEN {extraction_status}='Complete' THEN 'not_applicable' "
        f"WHEN UPPER({extraction_code}) LIKE 'DOCUMENT_%' THEN 'document' "
        f"WHEN UPPER({extraction_code}) LIKE 'PDF_%' THEN 'pdf' "
        f"WHEN UPPER({extraction_code}) LIKE 'IMAGE_%' THEN 'image' "
        f"WHEN UPPER({extraction_code}) LIKE 'MEDIA_%' THEN 'media' "
        f"WHEN UPPER({extraction_code}) LIKE 'TEXT_%' THEN 'text' "
        f"WHEN UPPER({extraction_code}) LIKE 'FORMAT_%' THEN 'format' ELSE 'other' END"
    )
    retry_state = (
        f"CASE WHEN {extraction_status}='Complete' THEN 'not_applicable' "
        f"WHEN CAST({extraction_retry} AS TEXT) IN ('false','0') THEN 'ineligible' "
        f"WHEN CAST({extraction_retry} AS TEXT) IN ('true','1') THEN 'eligible' "
        "ELSE 'unspecified' END"
    )
    destination_state = _evidence_state((
        "destination_drive_id", "destination_item_id",
        "destination_web_url", "destination_etag",
    ))
    archive_state = _evidence_state((
        "source_archive_item_id", "source_archive_web_url",
        "source_archive_etag", "source_archived_at",
    ))
    rows = conn.execute(
        "SELECT review_type,extraction_state,failure_family,decision_state,target_state,"
        "destination_state,archive_state,retry_state,COUNT(*) AS count FROM ("
        f"SELECT {review_type} AS review_type,"
        f"{normalized_extraction} AS extraction_state,{failure_family} AS failure_family,"
        "CASE WHEN c.decision='Approved' THEN 'approved' ELSE 'not_approved' END "
        "AS decision_state,CASE WHEN c.target_folder<>'' THEN 'configured' ELSE 'missing' END "
        f"AS target_state,{destination_state} AS destination_state,"
        f"{archive_state} AS archive_state,{retry_state} AS retry_state "
        "FROM m365_knowledge_candidates c WHERE c.status='Pending Review'"
        ") scoped GROUP BY review_type,extraction_state,failure_family,decision_state,"
        "target_state,destination_state,archive_state,retry_state"
    ).fetchall()
    allowed = {
        "review_type": {*expected_counts, "other"},
        "extraction_state": {"review_required", "complete", "other"},
        "failure_family": {
            "not_applicable", "document", "pdf", "image", "media", "text",
            "format", "other",
        },
        "decision_state": {"approved", "not_approved"},
        "target_state": {"configured", "missing"},
        "destination_state": {"none", "partial", "complete"},
        "archive_state": {"none", "partial", "complete"},
        "retry_state": {"not_applicable", "ineligible", "eligible", "unspecified"},
    }
    observed = {name: 0 for name in expected_counts}
    other = 0
    result: dict[str, int] = {}
    for row in rows:
        values = {name: str(row[name] or "") for name in allowed}
        if any(values[name] not in allowed[name] for name in allowed):
            raise RuntimeError("Pending-review category left the fixed boundary")
        count = int(row["count"] or 0)
        if values["review_type"] in observed:
            observed[values["review_type"]] += count
        else:
            other += count
        key = "_".join((
            "pending_fingerprint", values["review_type"],
            f"extraction_{values['extraction_state']}",
            f"failure_{values['failure_family']}",
            f"decision_{values['decision_state']}",
            f"target_{values['target_state']}",
            f"destination_{values['destination_state']}",
            f"archive_{values['archive_state']}",
            f"retry_{values['retry_state']}",
        ))
        result[key] = count
    if observed != expected_counts or other or sum(observed.values()) != EXPECTED_INITIAL_TOTAL:
        raise RuntimeError("Pending-review exact candidate scope changed")
    result.update({f"pending_scope_{name}": count for name, count in observed.items()})
    result.update({
        "pending_scope_total": sum(observed.values()),
        "pending_scope_other": other,
        "pending_scope_fingerprint_groups": len(rows),
        "source_reconciliation_unresolved": observed["source_reconciliation"],
    })
    return result


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


def collect_source_preflight(
    conn: Any,
    client: Any,
    headers: dict[str, str],
    *,
    drive_id: str,
    pending_id: str,
    enterprise_id: str,
    intake_root_id: str,
    expected_counts: dict[str, int] = EXPECTED_PROMOTION_SCOPE_COUNTS,
    expected_states: dict[tuple[str, str], int] | None = None,
    scan_missing_successors: bool = False,
) -> dict[str, int]:
    """Verify exact live source metadata and ancestry without reading bytes."""
    statuses = tuple(EXPECTED_PROMOTION_SCOPE_COUNTS)
    identifiers = (drive_id, pending_id, enterprise_id, intake_root_id)
    if tuple(expected_counts) != statuses or any(
        not _SOURCE_ID.fullmatch(value) for value in identifiers
    ):
        raise RuntimeError("Source-preflight boundary is invalid")
    extraction = _json_expression(conn, "extraction,status")
    marks = ",".join("?" for _ in statuses)
    rows = conn.execute(
        "SELECT c.source_drive_id,c.source_item_id,c.source_name,"
        "c.source_relative_path,c.source_etag,c.source_size,c.source_modified_at,"
        "c.status FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) AND {extraction}='Complete' ORDER BY c.id",
        statuses,
    ).fetchall()
    observed = {status: 0 for status in statuses}
    states = {
        "verified", "not_found", "drive_mismatch", "version_changed",
        "metadata_changed", "outside_pending", "route_missing", "ancestry_missing",
    }
    counts = {f"source_{_key(status)}_{state}": 0 for status in statuses for state in states}
    counts.update({
        f"source_{_key(status)}_outside_area_{area_key}": 0
        for status in statuses for area_key in SOURCE_AREA_KEYS.values()
    })
    endpoint = f"{GRAPH_ROOT}/drives/{drive_id}/items/"
    missing_rows = []
    for row in rows:
        status = str(row["status"] or "")
        item_id = str(row["source_item_id"] or "")
        if status not in observed or not _SOURCE_ID.fullmatch(item_id):
            raise RuntimeError("Source-preflight candidate boundary changed")
        observed[status] += 1
        duplicate_work = int(conn.execute(
            "SELECT COUNT(*) FROM m365_bulk_items WHERE drive_id=? AND item_id=?",
            (row["source_drive_id"], item_id),
        ).fetchone()[0] or 0)
        if duplicate_work:
            raise RuntimeError("Source-preflight durable-work boundary changed")
        if str(row["source_drive_id"] or "") != drive_id:
            state = "drive_mismatch"
        else:
            response = client.get(
                endpoint + item_id,
                headers=headers,
                params={"$select": (
                    "id,name,size,eTag,lastModifiedDateTime,parentReference,"
                    "file,remoteItem,webUrl"
                )},
            )
            if response.status_code == 404:
                state = "not_found"
                missing_rows.append(row)
            elif response.status_code != 200:
                raise RuntimeError("Source-preflight Microsoft Graph request failed")
            else:
                item = response.json()
                parent = str((item.get("parentReference") or {}).get("id", ""))
                web_url = str(item.get("webUrl", ""))
                parsed = urlparse(web_url)
                if (
                    item.get("id") != item_id or not isinstance(item.get("file"), dict)
                    or "remoteItem" in item or not _SOURCE_ID.fullmatch(parent)
                    or parsed.scheme != "https" or parsed.username or parsed.password
                    or not (parsed.hostname or "").lower().endswith(".sharepoint.com")
                ):
                    raise RuntimeError("Source-preflight Microsoft Graph response was invalid")
                if str(item.get("eTag", "")) != str(row["source_etag"] or ""):
                    state = "version_changed"
                elif (
                    str(item.get("name", "")) != str(row["source_name"] or "")
                    or int(item.get("size", -1)) != int(row["source_size"] or -1)
                    or str(item.get("lastModifiedDateTime", ""))
                    != str(row["source_modified_at"] or "")
                ):
                    state = "metadata_changed"
                else:
                    names = [str(item["name"])]
                    seen = {item_id}
                    routed = enterprise_id == pending_id or parent == enterprise_id
                    state = "verified"
                    while parent != pending_id:
                        if parent == intake_root_id:
                            if len(names) < 2 or names[-1] not in SOURCE_AREA_KEYS:
                                raise RuntimeError("Source-preflight outside area left the fixed boundary")
                            state = "outside_pending"
                            counts[
                                f"source_{_key(status)}_outside_area_"
                                f"{SOURCE_AREA_KEYS[names[-1]]}"
                            ] += 1
                            break
                        if parent in seen or len(seen) > 128:
                            raise RuntimeError("Source-preflight ancestry was invalid")
                        seen.add(parent)
                        ancestor = client.get(
                            endpoint + parent,
                            headers=headers,
                            params={
                                "$select": "id,name,parentReference,folder,remoteItem"
                            },
                        )
                        if ancestor.status_code == 404:
                            state = "ancestry_missing"
                            break
                        if ancestor.status_code != 200:
                            raise RuntimeError("Source-preflight ancestry request failed")
                        folder = ancestor.json()
                        next_parent = str(
                            (folder.get("parentReference") or {}).get("id", "")
                        )
                        name = str(folder.get("name", ""))
                        if (
                            folder.get("id") != parent
                            or not isinstance(folder.get("folder"), dict)
                            or "remoteItem" in folder
                            or not _SOURCE_ID.fullmatch(next_parent)
                            or not name or name in {".", ".."}
                            or "/" in name or "\\" in name
                        ):
                            raise RuntimeError("Source-preflight ancestry response was invalid")
                        routed = routed or parent == enterprise_id
                        names.append(name)
                        parent = next_parent
                    if state == "verified" and not routed:
                        state = "route_missing"
                    if state == "verified":
                        current_path = "10 Pending Classification/" + "/".join(
                            reversed(names)
                        )
                        if current_path != str(row["source_relative_path"] or ""):
                            state = "metadata_changed"
        if state not in states:
            raise RuntimeError("Source-preflight state left the fixed boundary")
        counts[f"source_{_key(status)}_{state}"] += 1
    if observed != expected_counts:
        raise RuntimeError("Source-preflight exact candidate scope changed")
    if expected_states is not None:
        actual_states = {
            (status, state): counts[f"source_{_key(status)}_{state}"]
            for status in statuses for state in states
            if counts[f"source_{_key(status)}_{state}"]
        }
        if actual_states != expected_states:
            raise RuntimeError("Source-preflight verified state changed")
    counts["source_scope_total"] = sum(observed.values())
    counts["source_verified_total"] = sum(
        counts[f"source_{_key(status)}_verified"] for status in statuses
    )
    counts["source_content_requests"] = 0
    counts["source_rows_changed"] = 0
    counts["source_outside_area_total"] = sum(
        counts[f"source_{_key(status)}_outside_area_{area_key}"]
        for status in statuses for area_key in SOURCE_AREA_KEYS.values()
    )
    counts["source_preflight_complete"] = 1
    if scan_missing_successors:
        counts.update(collect_missing_source_matches(
            client, headers, drive_id=drive_id, intake_root_id=intake_root_id,
            missing_rows=missing_rows,
        ))
    return counts


def collect_missing_source_matches(
    client: Any,
    headers: dict[str, str],
    *,
    drive_id: str,
    intake_root_id: str,
    missing_rows: list[Any],
    expected_boundary_files: int = EXPECTED_BOUNDARY_FILES,
) -> dict[str, int]:
    """Search governed metadata for unique successors without reading bytes."""
    if (
        not _SOURCE_ID.fullmatch(drive_id)
        or not _SOURCE_ID.fullmatch(intake_root_id)
        or len(missing_rows) != 5
        or expected_boundary_files < 1
    ):
        raise RuntimeError("Missing-source reconciliation boundary is invalid")
    exact = [0] * len(missing_rows)
    metadata = [0] * len(missing_rows)
    queue = deque([(intake_root_id, "")])
    seen_folders, seen_items, top_level = set(), set(), set()
    files = pages = 0
    select = "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,parentReference"
    while queue:
        folder_id, area = queue.popleft()
        if folder_id in seen_folders or len(seen_folders) >= MAX_BOUNDARY_FOLDERS:
            raise RuntimeError("Missing-source folder traversal is invalid")
        seen_folders.add(folder_id)
        endpoint = f"{GRAPH_ROOT}/drives/{drive_id}/items/{folder_id}/children"
        page, params, seen_pages = endpoint, {"$select": select, "$top": "200"}, set()
        while page:
            if page in seen_pages or pages >= MAX_BOUNDARY_PAGES:
                raise RuntimeError("Missing-source page traversal is invalid")
            seen_pages.add(page)
            pages += 1
            response = client.get(page, headers=headers, params=params)
            if response.status_code != 200:
                raise RuntimeError("Missing-source boundary folder is unavailable")
            payload = response.json()
            values = payload.get("value")
            if not isinstance(values, list) or len(values) > 1_000:
                raise RuntimeError("Missing-source boundary response is invalid")
            for item in values:
                if not isinstance(item, dict) or "remoteItem" in item:
                    raise RuntimeError("Missing-source boundary item is invalid")
                item_id = str(item.get("id", ""))
                name = str(item.get("name", ""))
                parent = str((item.get("parentReference") or {}).get("id", ""))
                if (
                    not _SOURCE_ID.fullmatch(item_id) or item_id in seen_items
                    or not name or name in {".", ".."} or "/" in name or "\\" in name
                    or parent != folder_id
                ):
                    raise RuntimeError("Missing-source boundary metadata is invalid")
                seen_items.add(item_id)
                if len(seen_items) > MAX_BOUNDARY_ITEMS:
                    raise RuntimeError("Missing-source boundary item limit exceeded")
                item_area = area or name
                if folder_id == intake_root_id:
                    top_level.add(name)
                is_folder = isinstance(item.get("folder"), dict)
                is_file = isinstance(item.get("file"), dict)
                if is_folder == is_file or item_area not in set(SOURCE_AREA_KEYS) | {
                    "10 Pending Classification"
                }:
                    raise RuntimeError("Missing-source boundary kind or area is invalid")
                if is_folder:
                    queue.append((item_id, item_area))
                    continue
                size = item.get("size")
                etag = str(item.get("eTag", ""))
                modified = str(item.get("lastModifiedDateTime", ""))
                if not isinstance(size, int) or size < 0 or not etag or not modified:
                    raise RuntimeError("Missing-source boundary provenance is incomplete")
                files += 1
                for index, row in enumerate(missing_rows):
                    if item_id == str(row["source_item_id"] or ""):
                        raise RuntimeError("Missing-source direct and census evidence conflict")
                    if (
                        name == str(row["source_name"] or "")
                        and size == int(row["source_size"] or -1)
                        and modified == str(row["source_modified_at"] or "")
                    ):
                        metadata[index] += 1
                        if etag == str(row["source_etag"] or ""):
                            exact[index] += 1
            next_page = payload.get("@odata.nextLink")
            if next_page:
                parsed, expected = urlparse(str(next_page)), urlparse(endpoint)
                if (
                    not isinstance(next_page, str) or len(next_page) > 8_192
                    or parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                    or parsed.username or parsed.password or parsed.fragment
                    or parsed.path != expected.path or not parsed.query
                ):
                    raise RuntimeError("Missing-source continuation left the boundary")
            page, params = (next_page, None) if next_page else ("", None)
    expected_areas = set(SOURCE_AREA_KEYS) | {"10 Pending Classification"}
    if top_level != expected_areas or files != expected_boundary_files:
        raise RuntimeError("Missing-source boundary identity or count changed")
    result = {
        "missing_successor_exact_unique": 0,
        "missing_successor_exact_ambiguous": 0,
        "missing_successor_metadata_unique": 0,
        "missing_successor_metadata_ambiguous": 0,
        "missing_successor_none": 0,
    }
    for exact_count, metadata_count in zip(exact, metadata):
        if exact_count == 1:
            key = "missing_successor_exact_unique"
        elif exact_count > 1:
            key = "missing_successor_exact_ambiguous"
        elif metadata_count == 1:
            key = "missing_successor_metadata_unique"
        elif metadata_count > 1:
            key = "missing_successor_metadata_ambiguous"
        else:
            key = "missing_successor_none"
        result[key] += 1
    result["missing_successor_scope_total"] = len(missing_rows)
    result["missing_successor_boundary_files"] = files
    result["missing_successor_content_requests"] = 0
    result["missing_successor_complete"] = 1
    return result


def _destination_names(name: str, sha256: str) -> tuple[str, str]:
    stem, separator, extension = name.rpartition(".")
    if not stem:
        stem, separator, extension = name, "", ""
    suffix = f".{sha256[:24]}" + (f".{extension}" if separator else "")
    primary = stem[:max(1, 240 - len(suffix))] + suffix
    fallback_suffix = f".{sha256}.original.bin"
    fallback = primary[:max(1, 240 - len(fallback_suffix))] + fallback_suffix
    return primary, fallback


def _read_destination_hash(
    writer: Any,
    folder_id: str,
    name: str,
    expected_sha256: str,
) -> tuple[str, int]:
    item_path = (
        f"{GRAPH_ROOT}/drives/{writer.destination.drive_id}/items/"
        f"{folder_id}:/{quote(name, safe='')}:"
    )
    response = writer.client.get(
        item_path,
        headers=writer._headers() | {"Accept": "application/json"},
        params={"$select": "id,name,size,eTag,parentReference,file,webUrl"},
    )
    if response.status_code == 404:
        return "missing", 0
    if response.status_code != 200:
        raise RuntimeError("Processed-evidence destination metadata request failed")
    item = response.json()
    item_id = str(item.get("id", ""))
    parent_id = str((item.get("parentReference") or {}).get("id", ""))
    size = int(item.get("size", -1))
    web_url = str(item.get("webUrl", ""))
    parsed = urlparse(web_url)
    if (
        not _SOURCE_ID.fullmatch(item_id)
        or item.get("name") != name
        or parent_id != folder_id
        or not isinstance(item.get("file"), dict)
        or size < 0 or size > writer.intake_config.max_file_bytes
        or parsed.scheme != "https" or parsed.username or parsed.password
        or not (parsed.hostname or "").lower().endswith(".sharepoint.com")
    ):
        raise RuntimeError("Processed-evidence destination metadata was invalid")
    download = writer.client.get(
        f"{GRAPH_ROOT}/drives/{writer.destination.drive_id}/items/{item_id}/content",
        headers=writer._headers() | {"Accept": "application/octet-stream"},
        timeout=120.0,
    )
    if download.status_code in {302, 303, 307, 308}:
        location = str(download.headers.get("Location", ""))
        parsed = urlparse(location)
        if (
            parsed.scheme != "https" or parsed.username or parsed.password
            or not (parsed.hostname or "").lower().endswith(".sharepoint.com")
        ):
            raise RuntimeError("Processed-evidence destination download was untrusted")
        download = writer.client.get(
            location, headers={"Accept": "application/octet-stream"}, timeout=120.0
        )
    if download.status_code != 200:
        raise RuntimeError("Processed-evidence destination content request failed")
    observed = hashlib.sha256(download.content).hexdigest()
    return ("exact" if observed == expected_sha256 else "mismatch"), 1


def _destination_evidence_state(
    writer: Any,
    folder_id: str,
    name: str,
    sha256: str,
) -> tuple[str, int]:
    primary, fallback = _destination_names(name, sha256)
    primary_state, downloads = _read_destination_hash(
        writer, folder_id, primary, sha256
    )
    if primary_state == "exact":
        return "exact", downloads
    fallback_state, fallback_downloads = _read_destination_hash(
        writer, folder_id, fallback, sha256
    )
    downloads += fallback_downloads
    if fallback_state == "exact":
        return "fallback_exact", downloads
    if primary_state == "missing" and fallback_state == "missing":
        return "missing", downloads
    return "mismatch", downloads


def collect_processed_evidence(
    conn: Any,
    writer: Any,
    expected_counts: dict[str, int] = EXPECTED_PROMOTION_SCOPE_COUNTS,
    expected_scope: int = EXPECTED_PROCESSED_EVIDENCE_SCOPE,
) -> dict[str, int]:
    """Hash-check four archived originals and their deterministic destinations."""
    statuses = tuple(EXPECTED_PROMOTION_SCOPE_COUNTS)
    if tuple(expected_counts) != statuses or sum(expected_counts.values()) != expected_scope:
        raise RuntimeError("Processed-evidence scope is invalid")
    writer.destination.validate()
    extraction = _json_expression(conn, "extraction,status")
    marks = ",".join("?" for _ in statuses)
    rows = conn.execute(
        "SELECT c.source_item_id,c.source_etag,c.source_sha256,c.source_name,"
        "c.target_folder,c.status FROM m365_knowledge_candidates c "
        f"WHERE c.status IN ({marks}) AND {extraction}='Complete' "
        "AND c.destination_drive_id='' AND c.destination_item_id='' "
        "AND c.destination_web_url='' AND c.destination_etag='' "
        "AND c.source_archive_item_id='' AND c.source_archive_web_url='' "
        "AND c.source_archive_etag='' AND c.source_archived_at='' "
        "AND NOT EXISTS (SELECT 1 FROM m365_bulk_items b "
        "WHERE b.drive_id=c.source_drive_id AND b.item_id=c.source_item_id) "
        "ORDER BY c.id",
        statuses,
    ).fetchall()
    observed = {status: 0 for status in statuses}
    destination_states = {state: 0 for state in (
        "exact", "fallback_exact", "missing", "mismatch",
    )}
    status_destination_states = {
        (status, state): 0
        for status in statuses for state in destination_states
    }
    folder_ids: dict[str, str] = {}
    content_downloads = 0
    for row in rows:
        status = str(row["status"] or "")
        item_id = str(row["source_item_id"] or "")
        sha256 = str(row["source_sha256"] or "")
        target = str(row["target_folder"] or "")
        if (
            status not in observed or not _SOURCE_ID.fullmatch(item_id)
            or not re.fullmatch(r"[0-9a-f]{64}", sha256)
            or not target
        ):
            raise RuntimeError("Processed-evidence candidate boundary changed")
        observed[status] += 1
        archived = writer.verify_already_archived_source(item_id, sha256)
        content_downloads += 1
        if (
            archived is None or archived.get("item_id") != item_id
            or str(archived.get("etag", "")) != str(row["source_etag"] or "")
        ):
            raise RuntimeError("Processed-evidence archived original changed")
        if target not in folder_ids:
            folder_ids[target] = writer._resolve_folder(target)
        state, downloads = _destination_evidence_state(
            writer, folder_ids[target], str(row["source_name"] or ""), sha256
        )
        destination_states[state] += 1
        status_destination_states[(status, state)] += 1
        content_downloads += downloads
    if observed != expected_counts or len(rows) != expected_scope:
        raise RuntimeError("Processed-evidence exact candidate scope changed")
    result = {
        "processed_evidence_scope_total": len(rows),
        "processed_evidence_archive_verified": len(rows),
        "processed_evidence_content_downloads": content_downloads,
        "processed_evidence_rows_changed": 0,
        "processed_evidence_complete": 1,
    }
    result.update({
        f"processed_evidence_destination_{state}": count
        for state, count in destination_states.items()
    })
    result.update({
        f"processed_evidence_status_{_key(status)}": count
        for status, count in observed.items()
    })
    result.update({
        f"processed_evidence_status_{_key(status)}_destination_{state}": count
        for (status, state), count in status_destination_states.items()
    })
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
    if observed != expected_status_counts:
        raise RuntimeError("Open-candidate exact checkpoint changed")
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

    source_reconciliations = int(conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates c WHERE "
        f"{_json_expression(conn, 'source_reconciliation,status')}='Review Required' "
        f"AND {_json_expression(conn, 'source_reconciliation,disposition')}=? "
        f"AND {_json_expression(conn, 'source_reconciliation,successor_match')}='None' "
        f"AND CAST({_json_expression(conn, 'source_reconciliation,boundary_files_rechecked')} "
        "AS TEXT)='22377'",
        (SOURCE_RECONCILIATION_DISPOSITION,),
    ).fetchone()[0] or 0)
    extraction_reviews = int(conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_candidates c WHERE c.status='Pending Review' "
        f"AND {_json_expression(conn, 'extraction,status')}='Review Required' "
        f"AND {_json_expression(conn, 'extraction,disposition')}=? "
        f"AND CAST({_json_expression(conn, 'extraction,retry_eligible')} AS TEXT) "
        "IN ('false','0')",
        (EXTRACTION_REVIEW_DISPOSITION,),
    ).fetchone()[0] or 0)
    if expected_status_counts is EXPECTED_INITIAL_STATUS_COUNTS and (
        extraction_reviews != EXPECTED_EXTRACTION_REVIEWS
        or source_reconciliations != EXPECTED_SOURCE_RECONCILIATIONS
        or event_counts["CandidateRoutedToGovernedExtractionReview"]
        != EXPECTED_EXTRACTION_REVIEWS
        or event_counts["CandidateRoutedToGovernedSourceReconciliation"]
        != EXPECTED_SOURCE_RECONCILIATIONS
    ):
        raise RuntimeError("Governed Pending Review checkpoint changed")

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
        "extraction_reviews": extraction_reviews,
        "source_reconciliations": source_reconciliations,
        "content_downloads": 0,
        "source_requests": 0,
        "rows_changed": 0,
        "protected_member_access_changes": 0,
        "assignment_changes": 0,
        "releases": 0,
    }
    result.update({f"status_{_key(status)}": count for status, count in observed.items()})
    result.update({f"matrix_{key}": count for key, count in matrix.items()})
    result.update({f"event_{_key(name)}": count for name, count in event_counts.items()})
    if expected_status_counts is EXPECTED_INITIAL_STATUS_COUNTS:
        result.update(_pending_review_fingerprints(conn))
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
