"""Pause repeated automatic extraction retries pending governed remediation.

The one-time transition changes metadata and retry scheduling only. It never
downloads source content, changes source access, or assigns a Protected Member.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any

from database import connect_database


EXPECTED_COUNTS = {
    "DOCUMENT_EXPANSION_LIMIT": 16,
    "IMAGE_METADATA_LIMIT": 1,
    "IMAGE_RESOURCE_LIMIT": 525,
    "MEDIA_RESOURCE_LIMIT": 139,
    "OCR_RESOURCE_LIMIT": 9,
    "PDF_PAGE_CONTENT_LIMIT": 2,
    "PDF_RESOURCE_LIMIT": 9,
    "PDF_SOURCE_LIMIT": 4,
    "TRANSCRIPT_OUTPUT_INVALID": 10,
    "TRANSCRIPTION_CAPACITY_UNAVAILABLE": 3,
    "TRANSCRIPTION_FAILED": 15,
}
EXPECTED_TOTAL = 733
PRIOR_STATUS = "Automatic Retry Required"
PAUSED_STATUS = "Retry Paused"
PAUSED_DISPOSITION = "Processor Remediation Required"
PAUSED_REASON = "repeated_retry_without_resolution"
PAUSED_FLAG = "Automatic Extraction Retry Paused - Processor Remediation Required"
PAUSE_UNTIL = 4_102_444_800  # 2100-01-01T00:00:00Z; resume requires governed release.
ACTOR = "SalCAPA Governed Retry Pause Worker"


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(classification_json,'$." + path.replace(",", ".") + "'),'')"


def _count_status(conn: Any, status: str) -> int:
    expression = _json_expression(conn, "extraction,status")
    return int(conn.execute(
        f"SELECT COUNT(*) FROM m365_knowledge_candidates WHERE {expression}=?",
        (status,),
    ).fetchone()[0] or 0)


def pause(
    conn: Any,
    expected_counts: dict[str, int] = EXPECTED_COUNTS,
    *,
    clock: int | None = None,
) -> dict[str, int]:
    """Atomically pause the exact approved retry set, failing on any drift."""
    clock = int(time.time() if clock is None else clock)
    status_expression = _json_expression(conn, "extraction,status")
    code_expression = _json_expression(conn, "extraction,failure_code")
    codes = tuple(sorted(expected_counts))
    marks = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"SELECT id,classification_json,{code_expression} AS failure_code "
        "FROM m365_knowledge_candidates "
        f"WHERE {status_expression}=? AND {code_expression} IN ({marks}) ORDER BY id",
        (PRIOR_STATUS, *codes),
    ).fetchall()
    observed = {code: 0 for code in codes}
    for row in rows:
        code = str(row["failure_code"] or "")
        if code not in observed:
            raise RuntimeError("Retry pause code left the approved boundary")
        observed[code] += 1
    if observed != expected_counts:
        raise RuntimeError("Retry pause pre-state changed")
    expected_total = sum(expected_counts.values())
    if expected_counts is EXPECTED_COUNTS and expected_total != EXPECTED_TOTAL:
        raise RuntimeError("Retry pause expectation is invalid")

    ids = tuple(int(row["id"]) for row in rows)
    id_marks = ",".join("?" for _ in ids)
    lock_sql = (
        "SELECT candidate_id,attempts,next_attempt,lease_owner,lease_until,last_code "
        f"FROM m365_bulk_extraction_checks WHERE candidate_id IN ({id_marks}) "
        "ORDER BY candidate_id"
    )
    if getattr(conn, "backend", "sqlite") == "postgres":
        lock_sql += " FOR UPDATE"
    checkpoints = conn.execute(lock_sql, ids).fetchall()
    if len(checkpoints) != expected_total:
        raise RuntimeError("Retry pause checkpoint coverage changed")
    if any(int(row["lease_until"] or 0) >= clock for row in checkpoints):
        raise RuntimeError("Retry pause found an active extraction lease")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed = events = schedules = 0
    try:
        for row in rows:
            classification = json.loads(row["classification_json"] or "{}")
            extraction = dict(classification.get("extraction") or {})
            code = str(extraction.get("failure_code") or "")
            if extraction.get("status") != PRIOR_STATUS or code not in expected_counts:
                raise RuntimeError("Retry pause candidate changed during transition")
            extraction.update({
                "status": PAUSED_STATUS,
                "retry_eligible": True,
                "automatic_retry_paused": True,
                "disposition": PAUSED_DISPOSITION,
                "disposition_reason": PAUSED_REASON,
                "paused_at": timestamp,
            })
            classification["extraction"] = extraction
            flags = [
                str(value) for value in classification.get("processing_flags", [])
                if str(value) != "Automatic Extraction Retry Required"
            ]
            if PAUSED_FLAG not in flags:
                flags.append(PAUSED_FLAG)
            classification["processing_flags"] = flags
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET classification_json=? "
                "WHERE id=? AND classification_json=?",
                (json.dumps(classification, sort_keys=True), row["id"], row["classification_json"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Retry pause lost its candidate concurrency guard")
            scheduled = conn.execute(
                "UPDATE m365_bulk_extraction_checks SET next_attempt=?,"
                "lease_owner='',lease_until=0 WHERE candidate_id=? AND lease_until<?",
                (PAUSE_UNTIL, row["id"], clock),
            )
            if scheduled.rowcount != 1:
                raise RuntimeError("Retry pause lost its checkpoint concurrency guard")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (
                    row["id"], "ExtractionAutomaticRetryPausedForProcessorRemediation", ACTOR,
                    json.dumps({
                        "failure_code": code,
                        "prior_status": PRIOR_STATUS,
                        "status": PAUSED_STATUS,
                        "retry_eligible": True,
                        "disposition": PAUSED_DISPOSITION,
                        "reason": PAUSED_REASON,
                        "resume_requires_governed_release": True,
                    }, sort_keys=True),
                    timestamp,
                ),
            )
            changed += 1
            schedules += 1
            events += 1
        paused_total = _count_status(conn, PAUSED_STATUS)
        automatic_remaining = _count_status(conn, PRIOR_STATUS)
        if changed != expected_total or paused_total != expected_total or automatic_remaining != 0:
            raise RuntimeError("Retry pause reconciliation is incomplete")
        paused_schedules = int(conn.execute(
            f"SELECT COUNT(*) FROM m365_bulk_extraction_checks "
            f"WHERE candidate_id IN ({id_marks}) AND next_attempt=?",
            (*ids, PAUSE_UNTIL),
        ).fetchone()[0] or 0)
        if paused_schedules != expected_total:
            raise RuntimeError("Retry pause schedule reconciliation is incomplete")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    result = {
        "paused": changed,
        "retry_eligible": changed,
        "audit_events": events,
        "schedules_paused": schedules,
        "automatic_remaining": automatic_remaining,
        "content_downloads": 0,
        "complete": int(changed == expected_total),
    }
    result.update({f"code_{code.lower()}": count for code, count in sorted(observed.items())})
    return result


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live retry-pause transition requires managed PostgreSQL")
    conn = connect_database()
    try:
        result = pause(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"RETRY_PAUSE_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
