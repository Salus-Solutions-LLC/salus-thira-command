"""Read-only aggregate reconciliation for the governed Salus Knowledge Library.

The probe emits counts and state flags only. It never selects names, paths,
content, attribution, identities, source bytes, or event details.
"""

from __future__ import annotations

import os
import re
import time
from collections import deque
from typing import Any
from urllib.parse import urlparse

from database import connect_database


EXPECTED_BOUNDARY_FILES = 22_377
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
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
MAX_BOUNDARY_ITEMS = 50_000
MAX_BOUNDARY_FOLDERS = 5_000
MAX_BOUNDARY_PAGES = 1_000
SOURCE_AREAS = {
    "10 Pending Classification": "PENDING",
    "20 Ready for Intake Review": "READY_REVIEW",
    "30 Exceptions and Manual Review": "EXCEPTIONS",
    "40 Customer Batch Staging - Unassigned": "CUSTOMER_STAGING",
    "90 Migration Hold": "MIGRATION_HOLD",
    "90 Processed Intake": "PROCESSED",
    "Does Not Upload": "DOES_NOT_UPLOAD",
}


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


def _json_field_expression(conn, path: str) -> str:
    if not re.fullmatch(r"[a-z_]+(?:,[a-z_]+)*", path):
        raise ValueError("JSON field path is outside the fixed probe allowlist")
    if getattr(conn, "backend", "sqlite") == "postgres":
        return f"COALESCE(classification_json::jsonb #>> '{{{path}}}','')"
    return "COALESCE(json_extract(classification_json,'$." + path.replace(",", ".") + "'),'')"


def _extraction_failure_categories(conn) -> dict[str, int]:
    expression = _json_field_expression(conn, "extraction,failure_code")
    categories = {
        "none": 0, "document": 0, "pdf": 0, "image": 0,
        "media": 0, "source": 0, "other": 0,
    }
    for row in conn.execute(
        f"SELECT {expression} AS failure_code,COUNT(*) AS count "
        "FROM m365_knowledge_candidates "
        "WHERE classification_json LIKE '%Automatic Retry Required%' "
        "GROUP BY failure_code"
    ).fetchall():
        code = str(row["failure_code"] or "")
        count = int(row["count"])
        if not code:
            category = "none"
        elif code.startswith("DOCUMENT_"):
            category = "document"
        elif code.startswith("PDF_"):
            category = "pdf"
        elif code.startswith("IMAGE_"):
            category = "image"
        elif code.startswith(("AUDIO_", "VIDEO_", "MEDIA_")):
            category = "media"
        elif code.startswith("SOURCE_"):
            category = "source"
        else:
            category = "other"
        categories[category] += count
    return categories


def _represented_source_ids(conn) -> set[str]:
    return {
        str(row["source_item_id"])
        for row in conn.execute("""
            SELECT item_id AS source_item_id FROM m365_bulk_items
            WHERE kind='file' AND status<>'Removed'
            UNION
            SELECT source_item_id FROM m365_knowledge_candidates
        """).fetchall()
    }


def _scoped_children_link(link: object, endpoint: str) -> str:
    if not isinstance(link, str) or not link or len(link) > 8192:
        raise RuntimeError("Boundary continuation invalid")
    parsed, expected = urlparse(link), urlparse(endpoint)
    if (
        parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
        or parsed.username or parsed.password or parsed.fragment
        or parsed.path != expected.path or not parsed.query
    ):
        raise RuntimeError("Boundary continuation invalid")
    return link


def _source_area_reconciliation(
    intake: Any, represented: set[str],
) -> dict[str, int]:
    """Compare source IDs by approved top-level area without emitting an ID or name."""
    root_id = intake.config.folder_item_id
    queue = deque([(root_id, "")])
    seen_folders, seen_items, boundary_files = set(), set(), set()
    top_level = set()
    files = {code: 0 for code in SOURCE_AREAS.values()}
    gaps = {code: 0 for code in SOURCE_AREAS.values()}
    pages = 0
    select = "id,name,size,file,folder,remoteItem,lastModifiedDateTime,eTag,parentReference"
    while queue:
        folder_id, area = queue.popleft()
        if folder_id in seen_folders or len(seen_folders) >= MAX_BOUNDARY_FOLDERS:
            raise RuntimeError("Boundary folder traversal invalid")
        seen_folders.add(folder_id)
        endpoint = f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{folder_id}/children"
        page, params, seen_pages = endpoint, {"$select": select, "$top": "200"}, set()
        while page:
            if page in seen_pages or pages >= MAX_BOUNDARY_PAGES:
                raise RuntimeError("Boundary page traversal invalid")
            seen_pages.add(page)
            pages += 1
            response = intake.client.get(page, headers=intake._headers(), params=params)
            if response.status_code != 200:
                raise RuntimeError("Boundary folder unavailable")
            payload = response.json()
            values = payload.get("value")
            if not isinstance(values, list) or len(values) > 1000:
                raise RuntimeError("Boundary response incomplete")
            for item in values:
                if not isinstance(item, dict) or "remoteItem" in item:
                    raise RuntimeError("Boundary item invalid")
                item_id = str(item.get("id", ""))
                if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", item_id):
                    raise RuntimeError("Boundary item identity invalid")
                if item_id in seen_items:
                    continue
                seen_items.add(item_id)
                if len(seen_items) > MAX_BOUNDARY_ITEMS:
                    raise RuntimeError("Boundary item limit exceeded")
                name = str(item.get("name", ""))
                parent = str((item.get("parentReference") or {}).get("id", ""))
                if (not name or name in {".", ".."} or "/" in name or "\\" in name
                        or parent != folder_id):
                    raise RuntimeError("Boundary item metadata invalid")
                item_area = area or name
                if folder_id == root_id:
                    top_level.add(name)
                is_folder, is_file = isinstance(item.get("folder"), dict), isinstance(item.get("file"), dict)
                if is_folder == is_file or item_area not in SOURCE_AREAS:
                    raise RuntimeError("Boundary item kind or area invalid")
                if is_folder:
                    queue.append((item_id, item_area))
                    continue
                if not isinstance(item.get("size"), int) or not item.get("eTag") or not item.get("lastModifiedDateTime"):
                    raise RuntimeError("Boundary file provenance incomplete")
                code = SOURCE_AREAS[item_area]
                files[code] += 1
                boundary_files.add(item_id)
                if item_id not in represented:
                    gaps[code] += 1
            next_page = payload.get("@odata.nextLink")
            page = _scoped_children_link(next_page, endpoint) if next_page else ""
            params = None
    if top_level != set(SOURCE_AREAS) or len(boundary_files) != EXPECTED_BOUNDARY_FILES:
        raise RuntimeError("Boundary identity or count changed")
    result = {f"area_{code.lower()}_files": files[code] for code in sorted(files)}
    result.update({f"area_{code.lower()}_gap": gaps[code] for code in sorted(gaps)})
    result["area_gap_total"] = sum(gaps.values())
    result["represented_outside_boundary"] = len(represented - boundary_files)
    result["boundary_pages_rechecked"] = pages
    return result


def collect(conn, intake: Any | None = None) -> dict[str, int]:
    missing = sum(not _table_exists(conn, table) for table in REQUIRED_TABLES)
    if missing:
        return {"required_tables_missing": missing}

    bulk = _count_statuses(conn, "m365_bulk_items")
    candidates = _count_statuses(conn, "m365_knowledge_candidates")
    extraction = _extraction_counts(conn)
    failure_categories = _extraction_failure_categories(conn)
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
        "candidate_pending_review": candidates.get("Pending Review", 0),
        "candidate_approved_promotion": candidates.get("Approved for Promotion", 0),
        "candidate_automatic_retry": candidates.get("Automatic Retry Required", 0),
        "candidate_destination_verified": candidates.get("Destination Verified", 0),
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
    result.update({f"failure_{key}": value for key, value in failure_categories.items()})
    optional = {
        "bulk_extraction_checks": "m365_bulk_extraction_checks",
        "zip_jobs": "m365_zip_jobs",
        "zip_members": "m365_zip_member_index",
    }
    for key, table in optional.items():
        result[key] = _scalar(conn, f"SELECT COUNT(*) FROM {table}") if _table_exists(conn, table) else 0
    if _table_exists(conn, "m365_bulk_extraction_checks"):
        clock = int(time.time())
        result.update({
            "retry_attempts_1": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE attempts=1"),
            "retry_attempts_2": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE attempts=2"),
            "retry_attempts_3_5": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE attempts BETWEEN 3 AND 5"),
            "retry_attempts_6_plus": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE attempts>=6"),
            "retry_due": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE next_attempt<=?", (clock,)),
            "retry_backoff": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE next_attempt>?", (clock,)),
            "retry_code_extraction": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE last_code='extraction_retry_required'"),
            "retry_code_archive_read": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE last_code='archived_source_read_unavailable'"),
            "retry_code_archive_scope": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE last_code='archived_source_outside_verified_folder'"),
            "retry_code_other": _scalar(conn, "SELECT COUNT(*) FROM m365_bulk_extraction_checks WHERE last_code NOT IN ('','extraction_retry_required','archived_source_read_unavailable','archived_source_outside_verified_folder')"),
        })
    if intake is not None:
        result.update(_source_area_reconciliation(intake, _represented_source_ids(conn)))
    return result


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("The live ledger probe requires the managed PostgreSQL runtime")
    conn = connect_database()
    try:
        from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        result = collect(conn, intake=intake)
    finally:
        conn.close()
    for key in sorted(result):
        print(f"LEDGER_{key.upper()}={result[key]}", flush=True)
    complete = int(
        result.get("required_tables_missing") == 0
        and result.get("unrepresented_files") == 0
        and result.get("area_gap_total") == 0
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
