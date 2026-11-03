"""Aggregate-only live readback for corpus-wide Knowledge consideration."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone

from database import connect_database
from salcapa_knowledge_consideration import consider


EXPECTED_BOUNDARY_FILES = 22_377
ACTOR = "System Administrator - governed v3.267 release readback"
QUERY = "Salus Knowledge Library governed completion readback"


def _emit_coverage(receipt_id: str, coverage: dict[str, object]) -> None:
    print(f"KNOWLEDGE_CONSIDERATION_RECEIPT_ID={receipt_id}", flush=True)
    for key in (
        "boundary_files", "considered_files", "matched_files",
        "considered_without_match", "content_available_files",
        "metadata_only_or_unresolved_files", "governed_hold_files",
    ):
        print(
            f"KNOWLEDGE_CONSIDERATION_{key.upper()}={int(coverage[key])}",
            flush=True,
        )


def main() -> None:
    if os.getenv("SALUS_DB_BACKEND", "").strip().lower() != "postgres":
        raise RuntimeError("Live consideration readback requires managed PostgreSQL")
    stage = "connect_database"
    conn = connect_database()
    try:
        stage = "represented_boundary_precount"
        precheck_boundary = int(conn.execute("""
          WITH represented AS (
            SELECT item_id source_item_id FROM m365_bulk_items
            WHERE kind='file' AND status<>'Removed'
            UNION
            SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
          )
          SELECT COUNT(*) count FROM represented
        """).fetchone()["count"])
        print(
            f"KNOWLEDGE_CONSIDERATION_PRECHECK_BOUNDARY_FILES={precheck_boundary}",
            flush=True,
        )
        stage = "create_consideration_receipt"
        result = consider(
            conn, QUERY, ACTOR,
            datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        )
        coverage = result["coverage"]
        receipt_id = str(result["receipt_id"])
        _emit_coverage(receipt_id, coverage)
        stage = "receipt_identity"
        if not re.fullmatch(r"[0-9a-f-]{36}", receipt_id):
            raise RuntimeError("Consideration receipt identity is invalid")
        stage = "boundary_count"
        if int(coverage["boundary_files"]) != EXPECTED_BOUNDARY_FILES:
            raise RuntimeError("Knowledge boundary count changed")
        stage = "considered_count"
        if int(coverage["considered_files"]) != EXPECTED_BOUNDARY_FILES:
            raise RuntimeError("Not every represented file was considered")
        stage = "full_consideration_flag"
        if coverage["all_represented_files_considered"] is not True:
            raise RuntimeError("Full represented-file consideration was not recorded")
        stage = "protected_member_access"
        if result["protected_member_access"] is not False:
            raise RuntimeError("Protected Member access boundary changed")
        stage = "assignment_or_release_authority"
        if result["assignment_or_release_authority"] is not False:
            raise RuntimeError("Assignment or release authority changed")
        stage = "durable_receipt_readback"
        row = conn.execute(
            "SELECT boundary_count,considered_count,actor "
            "FROM m365_knowledge_consideration_receipts WHERE receipt_id=?",
            (receipt_id,),
        ).fetchone()
        if row is None or int(row["boundary_count"]) != EXPECTED_BOUNDARY_FILES:
            raise RuntimeError("Durable consideration receipt readback failed")
        if int(row["considered_count"]) != EXPECTED_BOUNDARY_FILES or row["actor"] != ACTOR:
            raise RuntimeError("Durable consideration receipt content changed")
    except Exception as exc:
        print(f"KNOWLEDGE_CONSIDERATION_FAILURE_STAGE={stage}", flush=True)
        print(f"KNOWLEDGE_CONSIDERATION_FAILURE_TYPE={type(exc).__name__}", flush=True)
        raise
    finally:
        conn.close()

    print("KNOWLEDGE_CONSIDERATION_ALL_REPRESENTED_FILES_CONSIDERED=1", flush=True)
    print("KNOWLEDGE_CONSIDERATION_PROTECTED_MEMBER_ACCESS=0", flush=True)
    print("KNOWLEDGE_CONSIDERATION_ASSIGNMENT_OR_RELEASE_AUTHORITY=0", flush=True)


if __name__ == "__main__":
    main()
