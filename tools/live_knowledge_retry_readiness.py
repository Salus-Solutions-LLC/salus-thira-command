"""Read-only readiness evidence for the remaining extraction retries.

This probe emits aggregate counts only. It never selects or logs a source
identifier, name, path, content, attribution, identity, URL, or event detail.
"""

from __future__ import annotations

import os
import time
from typing import Any

from database import connect_database


EXPECTED_INITIAL_COUNTS = {
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
EXPECTED_INITIAL_TOTAL = 733
RETRY_STATUS = "Automatic Retry Required"


def _json_expression(conn: Any, path: str) -> str:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(c.classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"


def _check_table_exists(conn: Any) -> bool:
    if getattr(conn, "backend", "sqlite") == "postgres":
        return bool(conn.execute(
            "SELECT to_regclass('m365_bulk_extraction_checks')"
        ).fetchone()[0])
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' "
        "AND name='m365_bulk_extraction_checks'"
    ).fetchone())


def collect(conn: Any, *, clock: int | None = None) -> dict[str, int]:
    """Collect bounded aggregate evidence and fail closed on scope drift."""
    clock = int(time.time() if clock is None else clock)
    status = _json_expression(conn, "extraction,status")
    code = _json_expression(conn, "extraction,failure_code")
    disposition = _json_expression(conn, "extraction,disposition")
    observed = {name: 0 for name in EXPECTED_INITIAL_COUNTS}
    unexpected = 0
    rows = conn.execute(
        f"SELECT {code} AS failure_code,COUNT(*) AS count "
        "FROM m365_knowledge_candidates c "
        f"WHERE {status}=? GROUP BY failure_code",
        (RETRY_STATUS,),
    ).fetchall()
    if len(rows) > 50:
        raise RuntimeError("Extraction retry code boundary exceeded")
    for row in rows:
        name = str(row["failure_code"] or "").upper()
        count = int(row["count"] or 0)
        if name not in observed:
            unexpected += count
            continue
        if count > EXPECTED_INITIAL_COUNTS[name]:
            raise RuntimeError("Extraction retry count exceeded its approved boundary")
        observed[name] = count
    if unexpected:
        raise RuntimeError("Extraction retry code left the approved boundary")

    remaining = sum(observed.values())
    if remaining > EXPECTED_INITIAL_TOTAL:
        raise RuntimeError("Extraction retry total exceeded its approved boundary")
    if not _check_table_exists(conn):
        raise RuntimeError("Extraction retry checkpoint table is missing")

    metrics = conn.execute(
        "SELECT COUNT(*) AS total,"
        "SUM(CASE WHEN r.candidate_id IS NULL THEN 1 ELSE 0 END) AS without_check,"
        "SUM(CASE WHEN COALESCE(r.next_attempt,0)<=? "
        "AND COALESCE(r.lease_until,0)<? THEN 1 ELSE 0 END) AS due,"
        "SUM(CASE WHEN COALESCE(r.next_attempt,0)>? "
        "AND COALESCE(r.lease_until,0)<? THEN 1 ELSE 0 END) AS backoff,"
        "SUM(CASE WHEN COALESCE(r.lease_until,0)>=? THEN 1 ELSE 0 END) AS leased,"
        "SUM(CASE WHEN COALESCE(r.attempts,0)=0 THEN 1 ELSE 0 END) AS attempts_0,"
        "SUM(CASE WHEN r.attempts=1 THEN 1 ELSE 0 END) AS attempts_1,"
        "SUM(CASE WHEN r.attempts=2 THEN 1 ELSE 0 END) AS attempts_2,"
        "SUM(CASE WHEN r.attempts BETWEEN 3 AND 5 THEN 1 ELSE 0 END) AS attempts_3_5,"
        "SUM(CASE WHEN r.attempts>=6 THEN 1 ELSE 0 END) AS attempts_6_plus "
        "FROM m365_knowledge_candidates c "
        "LEFT JOIN m365_bulk_extraction_checks r ON r.candidate_id=c.id "
        f"WHERE {status}=?",
        (clock, clock, clock, clock, clock, RETRY_STATUS),
    ).fetchone()
    result = {
        "remaining": remaining,
        "resolved_since_transition": EXPECTED_INITIAL_TOTAL - remaining,
        "unexpected": unexpected,
        "with_check": remaining - int(metrics["without_check"] or 0),
        "without_check": int(metrics["without_check"] or 0),
        "due": int(metrics["due"] or 0),
        "backoff": int(metrics["backoff"] or 0),
        "leased": int(metrics["leased"] or 0),
        "attempts_0": int(metrics["attempts_0"] or 0),
        "attempts_1": int(metrics["attempts_1"] or 0),
        "attempts_2": int(metrics["attempts_2"] or 0),
        "attempts_3_5": int(metrics["attempts_3_5"] or 0),
        "attempts_6_plus": int(metrics["attempts_6_plus"] or 0),
        "governed_review_overlap": int(conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates c "
            f"WHERE {status}=? AND {disposition}='Governed Extraction Review Required'",
            (RETRY_STATUS,),
        ).fetchone()[0] or 0),
        "content_downloads": 0,
        "complete": int(remaining == 0),
    }
    if int(metrics["total"] or 0) != remaining:
        raise RuntimeError("Extraction retry aggregate join changed the retry total")
    if result["due"] + result["backoff"] + result["leased"] != remaining:
        raise RuntimeError("Extraction retry schedule states do not reconcile")
    if sum(result[key] for key in (
        "attempts_0", "attempts_1", "attempts_2", "attempts_3_5", "attempts_6_plus"
    )) != remaining:
        raise RuntimeError("Extraction retry attempt states do not reconcile")
    if result["governed_review_overlap"]:
        raise RuntimeError("Extraction retry and governed-review states overlap")
    result.update({f"code_{name.lower()}": count for name, count in sorted(observed.items())})
    return result


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live retry-readiness probe requires managed PostgreSQL")
    conn = connect_database()
    try:
        result = collect(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"RETRY_READY_{key.upper()}={result[key]}", flush=True)


if __name__ == "__main__":
    main()
