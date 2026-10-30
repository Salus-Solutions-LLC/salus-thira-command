"""Reclassify deterministic extraction failures for governed human review.

This one-time transition reads and changes metadata only. It does not download
source content, alter source access, assign a Protected Member, or retry work.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from database import connect_database


EXPECTED_COUNTS = {
    "DOCUMENT_ACTIVE_CONTENT": 97,
    "DOCUMENT_ACTIVE_OR_LEGACY_FORMAT": 2307,
    "DOCUMENT_PACKAGE_INVALID": 29,
    "DOCUMENT_XML_INVALID": 2,
    "FORMAT_NOT_SUPPORTED": 2036,
    "IMAGE_FORMAT_MISMATCH": 45,
    "IMAGE_HEADER_INVALID": 3,
    "MEDIA_FORMAT_MISMATCH": 9,
    "MEDIA_HEADER_INVALID": 1,
    "MEDIA_STREAM_INVALID": 10,
    "MEDIA_STREAM_LIMIT": 2,
    "PDF_ACTIVE_CONTENT": 2295,
    "PDF_ENCRYPTED": 226,
    "PDF_HEADER_INVALID": 14,
    "PDF_PAGE_LIMIT": 3,
    "PDF_PARSE_FAILED": 3,
    "TEXT_ENCODING_UNSUPPORTED": 34,
}
EXPECTED_RECLASSIFIED = 7_116
EXPECTED_RETRY_REMAINING = 733
REVIEW_STATUS = "Review Required"
REVIEW_DISPOSITION = "Governed Extraction Review Required"
REVIEW_REASON = "deterministic_source_or_policy_condition"
ACTOR = "SalCAPA Governed Extraction Review Worker"


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(classification_json,'$." + path.replace(",", ".") + "'),'')"


def _count_status(conn: Any, status: str) -> int:
    expression = _json_expression(conn, "extraction,status")
    return int(conn.execute(
        f"SELECT COUNT(*) FROM m365_knowledge_candidates WHERE {expression}=?",
        (status,),
    ).fetchone()[0])


def reclassify(conn: Any, expected_counts: dict[str, int] = EXPECTED_COUNTS) -> dict[str, int]:
    if sum(expected_counts.values()) <= 0:
        raise RuntimeError("Extraction review expectation is invalid")
    status_expression = _json_expression(conn, "extraction,status")
    code_expression = _json_expression(conn, "extraction,failure_code")
    codes = tuple(sorted(expected_counts))
    marks = ",".join("?" for _ in codes)
    rows = conn.execute(
        f"SELECT id,classification_json,{code_expression} AS failure_code "
        "FROM m365_knowledge_candidates "
        f"WHERE {status_expression}=? AND {code_expression} IN ({marks}) ORDER BY id",
        ("Automatic Retry Required", *codes),
    ).fetchall()
    observed = {code: 0 for code in codes}
    for row in rows:
        code = str(row["failure_code"])
        if code not in observed:
            raise RuntimeError("Extraction review code left the approved boundary")
        observed[code] += 1
    if observed != expected_counts:
        raise RuntimeError("Extraction review pre-state changed")

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    changed = events = 0
    try:
        for row in rows:
            classification = json.loads(row["classification_json"] or "{}")
            extraction = dict(classification.get("extraction") or {})
            code = str(extraction.get("failure_code", ""))
            if extraction.get("status") != "Automatic Retry Required" or code not in expected_counts:
                raise RuntimeError("Extraction review candidate changed during transition")
            extraction.update({
                "status": REVIEW_STATUS,
                "retry_eligible": False,
                "disposition": REVIEW_DISPOSITION,
                "disposition_reason": REVIEW_REASON,
            })
            classification["extraction"] = extraction
            flags = [
                str(value) for value in classification.get("processing_flags", [])
                if str(value) != "Automatic Extraction Retry Required"
            ]
            if REVIEW_DISPOSITION not in flags:
                flags.append(REVIEW_DISPOSITION)
            classification["processing_flags"] = flags
            updated_json = json.dumps(classification, sort_keys=True)
            updated = conn.execute(
                "UPDATE m365_knowledge_candidates SET classification_json=? "
                "WHERE id=? AND classification_json=?",
                (updated_json, row["id"], row["classification_json"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("Extraction review transition lost its concurrency guard")
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (
                    row["id"], "ExtractionRetryReclassifiedForGovernedReview", ACTOR,
                    json.dumps({
                        "failure_code": code,
                        "prior_status": "Automatic Retry Required",
                        "status": REVIEW_STATUS,
                        "disposition": REVIEW_DISPOSITION,
                        "reason": REVIEW_REASON,
                    }, sort_keys=True),
                    timestamp,
                ),
            )
            changed += 1
            events += 1
        review_total = _count_status(conn, REVIEW_STATUS)
        retry_remaining = _count_status(conn, "Automatic Retry Required")
        expected_total = sum(expected_counts.values())
        if changed != expected_total or review_total != expected_total:
            raise RuntimeError("Extraction review reconciliation is incomplete")
        if expected_counts is EXPECTED_COUNTS and retry_remaining != EXPECTED_RETRY_REMAINING:
            raise RuntimeError("Extraction retry remainder changed")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    result = {
        "reclassified": changed,
        "audit_events": events,
        "review_required": review_total,
        "retry_remaining": retry_remaining,
        "content_downloads": 0,
        "complete": int(changed == sum(expected_counts.values())),
    }
    result.update({f"code_{code.lower()}": count for code, count in sorted(observed.items())})
    return result


def main() -> None:
    conn = connect_database()
    try:
        result = reclassify(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"REVIEW_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
