"""Read-only aggregate reconciliation for the governed Salus Knowledge Library.

The probe emits counts and state flags only. It never selects names, paths,
content, attribution, identities, source bytes, or event details.
"""

from __future__ import annotations

import os

from database import connect_database


EXPECTED_BOUNDARY_FILES = 22_377
REQUIRED_TABLES = (
    "m365_bulk_cursors",
    "m365_bulk_items",
    "m365_knowledge_candidates",
)
BULK_OPEN = ("Pending", "Retry", "Working", "Assignment Required")
CANDIDATE_OPEN = (
    "Pending Review",
    "Approved for Promotion",
    "Automatic Retry Required",
    "Destination Verified",
)


def _scalar(conn, sql: str, params=()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0] or 0)


def _table_exists(conn, table: str) -> bool:
    if table not in REQUIRED_TABLES and table not in {
        "m365_bulk_extraction_checks", "m365_zip_jobs", "m365_zip_member_index"
    }:
        raise ValueError("Ledger table is outside the fixed probe allowlist")
    if getattr(conn, "backend", "sqlite") == "postgres":
        return bool(conn.execute("SELECT to_regclass(?)", (table,)).fetchone()[0])
    return bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone())


def _count_statuses(conn, table: str) -> dict[str, int]:
    if table not in {"m365_bulk_items", "m365_knowledge_candidates"}:
        raise ValueError("Status table is outside the fixed probe allowlist")
    return {
        str(row["status"]): int(row["count"])
        for row in conn.execute(
            f"SELECT status,COUNT(*) AS count FROM {table} GROUP BY status"
        ).fetchall()
    }


def _extraction_counts(conn) -> dict[str, int]:
    if getattr(conn, "backend", "sqlite") == "postgres":
        expression = "COALESCE(classification_json::jsonb #>> '{extraction,status}','')"
    else:
        expression = "COALESCE(json_extract(classification_json,'$.extraction.status'),'')"
    return {
        str(row["extraction_status"]): int(row["count"])
        for row in conn.execute(
            f"SELECT {expression} AS extraction_status,COUNT(*) AS count "
            "FROM m365_knowledge_candidates GROUP BY extraction_status"
        ).fetchall()
    }


def collect(conn) -> dict[str, int]:
    missing = sum(not _table_exists(conn, table) for table in REQUIRED_TABLES)
    if missing:
        return {"required_tables_missing": missing}

    bulk = _count_statuses(conn, "m365_bulk_items")
    candidates = _count_statuses(conn, "m365_knowledge_candidates")
    extraction = _extraction_counts(conn)
    represented = _scalar(conn, """
        SELECT COUNT(*) FROM (
          SELECT item_id AS source_item_id FROM m365_bulk_items
          WHERE kind='file' AND status<>'Removed'
          UNION
          SELECT source_item_id FROM m365_knowledge_candidates
        ) represented
    """)
    bulk_files = _scalar(
        conn, "SELECT COUNT(*) FROM m365_bulk_items WHERE kind='file'"
    )
    bulk_active_files = _scalar(
        conn,
        "SELECT COUNT(*) FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'",
    )
    cursor_total = _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_cursors")
    cursor_delta = _scalar(
        conn, "SELECT COUNT(*) FROM m365_bulk_cursors WHERE phase='delta'"
    )
    cursor_errors = _scalar(
        conn, "SELECT COUNT(*) FROM m365_bulk_cursors WHERE last_error<>''"
    )
    result = {
        "required_tables_missing": 0,
        "boundary_files": EXPECTED_BOUNDARY_FILES,
        "represented_distinct_files": represented,
        "unrepresented_files": max(0, EXPECTED_BOUNDARY_FILES - represented),
        "represented_above_boundary": int(represented > EXPECTED_BOUNDARY_FILES),
        "bulk_rows": sum(bulk.values()),
        "bulk_file_rows": bulk_files,
        "bulk_active_file_rows": bulk_active_files,
        "bulk_open": sum(bulk.get(status, 0) for status in BULK_OPEN),
        "bulk_done": bulk.get("Done", 0),
        "bulk_oversize": bulk.get("Oversize", 0),
        "bulk_removed": bulk.get("Removed", 0),
        "bulk_directory": bulk.get("Directory", 0),
        "bulk_unexpected_status": sum(
            count for status, count in bulk.items()
            if status not in set(BULK_OPEN) | {"Done", "Oversize", "Removed", "Directory"}
        ),
        "candidate_rows": sum(candidates.values()),
        "candidate_ingested_verified": candidates.get("Ingested and Verified", 0),
        "candidate_open": sum(candidates.get(status, 0) for status in CANDIDATE_OPEN),
        "candidate_other": sum(
            count for status, count in candidates.items()
            if status not in set(CANDIDATE_OPEN) | {
                "Ingested and Verified", "Promoted", "Source Retained", "Source Removed"
            }
        ),
        "extraction_complete": extraction.get("Complete", 0),
        "extraction_retry": extraction.get("Automatic Retry Required", 0),
        "extraction_review": extraction.get("Review Required", 0),
        "extraction_missing": extraction.get("", 0),
        "extraction_other": sum(
            count for status, count in extraction.items()
            if status not in {"", "Complete", "Automatic Retry Required", "Review Required"}
        ),
        "cursor_total": cursor_total,
        "cursor_delta": cursor_delta,
        "cursor_errors": cursor_errors,
    }
    optional = {
        "bulk_extraction_checks": "m365_bulk_extraction_checks",
        "zip_jobs": "m365_zip_jobs",
        "zip_members": "m365_zip_member_index",
    }
    for key, table in optional.items():
        result[key] = _scalar(conn, f"SELECT COUNT(*) FROM {table}") if _table_exists(conn, table) else 0
    return result


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live ledger probe requires the managed PostgreSQL runtime")
    conn = connect_database()
    try:
        result = collect(conn)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"LEDGER_{key.upper()}={result[key]}", flush=True)
    complete = int(
        result.get("required_tables_missing") == 0
        and result.get("unrepresented_files") == 0
        and result.get("represented_above_boundary") == 0
        and result.get("bulk_open") == 0
        and result.get("candidate_open") == 0
        and result.get("extraction_retry") == 0
        and result.get("extraction_review") == 0
        and result.get("extraction_missing") == 0
        and result.get("extraction_other") == 0
        and result.get("cursor_errors") == 0
    )
    print(f"RECONCILIATION_COMPLETE={complete}", flush=True)


if __name__ == "__main__":
    main()
