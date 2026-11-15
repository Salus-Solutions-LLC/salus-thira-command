"""Task-bound, aggregate-only Knowledge consideration and durable receipt proof."""

from __future__ import annotations

import hashlib
import os
import re
from datetime import datetime, timezone

from salcapa_knowledge_consideration import consider


TASK_KEY = "salus-search-and-chat-capture-20261114"
ACTOR = "System Administrator - task consideration " + TASK_KEY
QUERIES = (
    ("source_retrieval", "knowledge management information retrieval evidence synthesis research methodology source evaluation"),
    ("search_quality", "search strategy systematic review literature review provenance source qualification"),
    ("records_learning", "records management document retention audit trail lessons learned knowledge transfer"),
    ("chat_capture", "chat conversation transcript capture strategies concepts methodologies"),
)


def snapshot(conn):
    current = {str(row["source_item_id"]) for row in conn.execute(
        "SELECT DISTINCT item_id source_item_id FROM m365_bulk_items "
        "WHERE kind='file' AND status<>'Removed'"
    ).fetchall()}
    represented = {str(row["source_item_id"]) for row in conn.execute("""
        SELECT source_item_id FROM m365_knowledge_candidates
        UNION SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
        UNION SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
    """).fetchall()}
    digest = hashlib.sha256(("\n".join(sorted(current)) + "\n--represented--\n" +
                             "\n".join(sorted(represented))).encode()).hexdigest()
    return len(current), len(represented), digest


def verify_receipt(conn, result, query, actor, created_at, boundary, represented):
    coverage = result["coverage"]
    receipt_id = str(result["receipt_id"])
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", receipt_id):
        raise RuntimeError("Receipt identity is invalid")
    expected_hash = hashlib.sha256(query.strip().encode()).hexdigest()
    if result["query_sha256"] != expected_hash:
        raise RuntimeError("Receipt query changed")
    if (coverage["boundary_files"], coverage["represented_files"],
            coverage["considered_files"]) != (boundary, represented, represented):
        raise RuntimeError("Receipt does not cover the live boundary")
    if coverage["historical_additional_representations"] != represented - boundary:
        raise RuntimeError("Additional representations do not reconcile")
    if coverage["matched_files"] + coverage["considered_without_match"] != represented:
        raise RuntimeError("Match dispositions do not reconcile")
    if coverage["content_available_files"] + coverage["metadata_only_or_unresolved_files"] != represented:
        raise RuntimeError("Availability dispositions do not reconcile")
    if not 0 <= coverage["governed_hold_files"] <= represented:
        raise RuntimeError("Hold count is invalid")
    if not (coverage["all_boundary_files_considered"] is True and
            coverage["all_represented_files_considered"] is True):
        raise RuntimeError("Full consideration flags are absent")
    if result["protected_member_access"] is not False or result["assignment_or_release_authority"] is not False:
        raise RuntimeError("Access or authority boundary changed")
    if not 0 <= len(result["results"]) <= min(100, coverage["matched_files"]):
        raise RuntimeError("Bounded candidate result count is invalid")
    row = conn.execute(
        "SELECT * FROM m365_knowledge_consideration_receipts WHERE receipt_id=?",
        (receipt_id,),
    ).fetchone()
    expected = {
        "query_sha256": expected_hash, "boundary_count": boundary,
        "considered_count": represented, "matched_count": coverage["matched_files"],
        "content_available_count": coverage["content_available_files"],
        "metadata_only_count": coverage["metadata_only_or_unresolved_files"],
        "governed_hold_count": coverage["governed_hold_files"],
        "actor": actor, "created_at": created_at,
    }
    if row is None or any(row[key] != value for key, value in expected.items()):
        raise RuntimeError("Durable receipt readback disagrees")
    return coverage


def run_search(conn, *, minimum_boundary=22377, minimum_represented=22399,
               queries=QUERIES, consider_fn=consider):
    pre = snapshot(conn)
    boundary, represented, _digest = pre
    if boundary < minimum_boundary or represented < minimum_represented:
        raise RuntimeError("Live source or representation count is below the governed minimum")
    if conn.execute(
        "SELECT COUNT(*) count FROM m365_knowledge_consideration_receipts WHERE actor LIKE ?",
        (ACTOR + " / %",),
    ).fetchone()["count"]:
        raise RuntimeError("This task already has receipts; do not blindly repeat it")
    print(f"TASK_KNOWLEDGE_PRECHECK_BOUNDARY_FILES={boundary}", flush=True)
    print(f"TASK_KNOWLEDGE_PRECHECK_REPRESENTED_FILES={represented}", flush=True)
    previous = os.environ.get("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES")
    summaries = []
    try:
        # The approved service accepts its boundary through this variable. Bind it
        # to the observed live source ledger, rather than a historical constant.
        os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = str(boundary)
        for number, (label, query) in enumerate(queries, 1):
            if snapshot(conn) != pre:
                raise RuntimeError("Source membership changed during task consideration")
            actor = ACTOR + " / " + label
            created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            result = consider_fn(conn, query, actor, created_at)
            coverage = verify_receipt(conn, result, query, actor, created_at, boundary, represented)
            if snapshot(conn) != pre:
                raise RuntimeError("Source membership changed during task consideration")
            # Only aggregate data and audit identifiers leave the isolated job.
            summary = {"query_number": number, "receipt_id": result["receipt_id"],
                       "query_sha256": result["query_sha256"], **coverage,
                       "bounded_candidate_results": len(result["results"])}
            summaries.append(summary)
            prefix = f"TASK_KNOWLEDGE_Q{number}_"
            for key, value in summary.items():
                if isinstance(value, bool):
                    value = int(value)
                print(f"{prefix}{key.upper()}={value}", flush=True)
        if snapshot(conn) != pre:
            raise RuntimeError("Final source membership changed")
    finally:
        if previous is None:
            os.environ.pop("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES", None)
        else:
            os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = previous
    print(f"TASK_KNOWLEDGE_VERIFIED_RECEIPTS={len(summaries)}", flush=True)
    print("TASK_KNOWLEDGE_SOURCE_MEMBERSHIP_STABLE=1", flush=True)
    print("TASK_KNOWLEDGE_PROTECTED_MEMBER_ACCESS=0", flush=True)
    print("TASK_KNOWLEDGE_ASSIGNMENT_OR_RELEASE_AUTHORITY=0", flush=True)
    print("TASK_KNOWLEDGE_COMPLETE=1", flush=True)
    return summaries


def main():
    if os.getenv("SALUS_DB_BACKEND", "").lower() != "postgres":
        raise RuntimeError("Managed PostgreSQL is required")
    from database import connect_database
    conn = connect_database()
    try:
        run_search(conn)
    except Exception as exc:
        # Do not emit database values, source names, paths, contents or exception
        # details into telemetry. A partial receipt is not a complete task run.
        print(f"TASK_KNOWLEDGE_FAILURE_TYPE={type(exc).__name__}", flush=True)
        raise SystemExit(1) from None
    finally:
        conn.close()


if __name__ == "__main__":
    main()
