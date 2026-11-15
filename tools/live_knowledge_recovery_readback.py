"""Read-only reconciliation of one consumed recovery-planning operation."""
from __future__ import annotations
import hashlib
import json
import os
import re

OPERATION = "salus-availability-recovery-plan-20261115"
ACTOR = "System Administrator - task consideration " + OPERATION + " / "
QUERIES = (
    ("availability_reconciliation", "extraction availability complete text provenance archive version discrepancy"),
    ("recovery_batches", "governed recovery review retry paused processor failure checkpoint batch"),
    ("safety_and_contrary", "hold restrictions source rights conflict unsafe document original derivative"),
    ("verification", "recovery manifest audit receipt stability cleanup independent verification"),
)
CATEGORIES = {"governed_review": 7085, "retry_paused": 733, "automatic_retry": 488,
              "governed_hold": 93, "other_or_conflicting": 5, "complete_without_text": 0, "no_candidate": 0}
TABLES = ("m365_knowledge_recovery_plans", "m365_knowledge_recovery_batches", "m365_knowledge_recovery_plan_events")
STATE = "Prepared - Not Authorized for Processing"
STAGE = "not_started"


def require(ok, code):
    if not ok:
        raise ValueError(code)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def exists(conn, table):
    require(table in TABLES, "TABLE_SCOPE")
    if getattr(conn, "backend", "sqlite") == "postgres":
        return bool(conn.execute("SELECT to_regclass(?)", (table,)).fetchone()[0])
    return bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())


def begin_read_only(conn):
    if getattr(conn, "backend", "sqlite") == "postgres":
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='60s'")
    else:
        conn.execute("PRAGMA query_only=ON")
        conn.execute("BEGIN")


def reconcile(conn):
    """Inspect committed rows only; this function never creates missing evidence."""
    global STAGE
    STAGE = "read_only_transaction"
    begin_read_only(conn)
    STAGE = "receipt_readback"
    receipts = [dict(r) for r in conn.execute(
        "SELECT * FROM m365_knowledge_consideration_receipts WHERE actor LIKE ? ORDER BY actor", (ACTOR + "%",)).fetchall()]
    require(len(receipts) <= 4, "RECEIPT_COUNT")
    expected = {ACTOR + label: hashlib.sha256(query.encode()).hexdigest() for label, query in QUERIES}
    seen = set()
    for r in receipts:
        require(r["actor"] in expected and r["actor"] not in seen, "RECEIPT_ACTOR")
        seen.add(r["actor"])
        require(r["query_sha256"] == expected[r["actor"]], "RECEIPT_QUERY")
        require(bool(re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", r["receipt_id"])), "RECEIPT_ID")
        require(r["boundary_count"] >= 22447 and r["considered_count"] == 23632 and
                r["content_available_count"] == 15228 and r["metadata_only_count"] == 8404 and
                r["governed_hold_count"] == 93 and 0 <= r["matched_count"] <= r["considered_count"], "RECEIPT_COUNTS")
        require(bool(re.fullmatch(r"2026-11-15T[0-9:]{8}\+00:00", r["created_at"])), "RECEIPT_TIME")
    require(len({r["boundary_count"] for r in receipts}) <= 1, "RECEIPT_BOUNDARY")
    require(len({r["receipt_id"] for r in receipts}) == len(receipts), "RECEIPT_DUPLICATE")
    STAGE = "planning_table_readback"
    present = {t: exists(conn, t) for t in TABLES}
    rows = {t: [dict(r) for r in conn.execute("SELECT * FROM " + t + " WHERE operation_key=?", (OPERATION,)).fetchall()]
            if present[t] else [] for t in TABLES}
    plans, batches, events = (rows[t] for t in TABLES)
    require(len(plans) <= 1 and len(events) <= 1 and len(batches) <= 8404, "PLANNING_COUNTS")
    result = {"operation_key": OPERATION, "receipt_count": len(receipts), "receipts": receipts,
              "plan_count": len(plans), "batch_count": len(batches), "event_count": len(events),
              "complete_preparation_verified": False, "durable_state": "EMPTY" if not receipts else "PARTIAL_RECEIPTS"}
    if not plans:
        require(not batches and not events, "ORPHAN_PLANNING_ROWS")
        return result
    require(all(present.values()) and len(events) == 1 and len(receipts) == 4, "PARTIAL_PREPARATION")
    STAGE = "manifest_hash_readback"
    row = plans[0]
    manifest = json.loads(row["payload_json"])
    require(canonical(manifest) == row["payload_json"] and digest(manifest) == row["manifest_sha256"], "MANIFEST_HASH")
    require(manifest["operation_key"] == OPERATION and row["state"] == manifest["state"] == STATE and
            row["created_at"] == manifest["created_at"], "MANIFEST_BINDING")
    require(bool(re.fullmatch(r"2026-11-15T[0-9:]{8}\+00:00", manifest["created_at"])), "MANIFEST_TIME")
    require(all(re.fullmatch(r"[0-9a-f]{64}", manifest[k]) for k in ("inventory_sha256", "evidence_sha256")), "SOURCE_HASH")
    summary = manifest["summary"]
    require(summary["categories"] == CATEGORIES and summary["unresolved_files"] == summary["prepared_sources"] == 8404 and
            summary["represented_files"] == 23632 and summary["legacy_content_available"] == 15228 and
            summary["exact_complete_nonempty_text"] == summary["strict_complete_text"] == 15223 and
            summary["availability_exceptions"] == 5 and summary["processing_authorized"] is False and
            summary["batch_count"] == len(batches), "MANIFEST_COUNTS")
    STAGE = "exact_batch_readback"
    hashes = manifest["batch_hashes"]
    require(len(hashes) == len(batches) and len({r["batch_key"] for r in hashes}) == len(batches), "BATCH_HASH_COUNT")
    hashes = {r["batch_key"]: r["sha256"] for r in hashes}
    source_ids, categories, conditions = set(), {k: 0 for k in CATEGORIES}, {}
    for b in batches:
        payload = json.loads(b["payload_json"])
        require(canonical(payload) == b["payload_json"] and digest(payload) == b["payload_sha256"] == hashes.get(b["batch_key"]), "BATCH_HASH")
        records = payload["records"]
        require(payload["batch_key"] == b["batch_key"] and payload["state"] == STATE and payload["processing_authorized"] is False and
                1 <= b["record_count"] == payload["record_count"] == len(records) <= 50, "BATCH_BINDING")
        for r in records:
            require(r["source_item_id"] not in source_ids and r["category"] == payload["category"] and
                    r["failure_codes"] == payload["failure_codes"] and r["category"] in categories and
                    r["processing_authorized"] is False and r["human_qualification"] == "Unvetted Candidate", "SOURCE_PARTITION")
            source_ids.add(r["source_item_id"])
            categories[r["category"]] += 1
            statuses = {c["extraction_status"] for c in r["candidate_versions"]}
            category = ("governed_hold" if r["holds"] else "other_or_conflicting" if len(statuses) > 1 else
                {"Review Required": "governed_review", "Retry Paused": "retry_paused", "Automatic Retry Required": "automatic_retry"}.get(next(iter(statuses), "")))
            require(category == r["category"], "SOURCE_CATEGORY")
            for c in r["candidate_versions"]:
                require(c["source_item_id"] == r["source_item_id"] and c["archive_bytes_verified_by_this_task"] is False and
                        not c["legacy_complete"], "CANDIDATE_BINDING")
    require(len(source_ids) == 8404 and categories == CATEGORIES, "SOURCE_COUNT")
    exceptions = manifest["availability_exceptions"]
    exception_ids = {r["source_item_id"] for r in exceptions}
    require(len(exceptions) == len(exception_ids) == 5 and not exception_ids & source_ids, "EXCEPTION_PARTITION")
    for r in exceptions:
        require(r["processing_authorized"] is False and r["human_qualification"] == "Unvetted Candidate", "EXCEPTION_AUTHORITY")
        for c in r["candidate_versions"]:
            require(c["source_item_id"] == r["source_item_id"], "EXCEPTION_CANDIDATE")
            expected_condition = ("EXACT_COMPLETE_EMPTY_TEXT" if c["legacy_complete"] and c["extraction_status"] == "Complete" else
                "BROAD_COMPLETE_MATCH_OUTSIDE_EXTRACTION_STATUS" if c["legacy_complete"] else "NOT_COUNTED_BY_LEGACY_PREDICATE")
            require(c["availability_condition"] == expected_condition and not (c["extraction_status"] == "Complete" and c["has_text"]), "EXCEPTION_CONDITION")
            conditions[expected_condition] = conditions.get(expected_condition, 0) + 1
    require(conditions == summary["availability_candidate_conditions"], "EXCEPTION_COUNTS")
    STAGE = "audit_event_readback"
    event = events[0]
    require(event["event_type"] == "AvailabilityReconciledAndRecoveryBatchesPrepared" and event["created_at"] == row["created_at"] and
            event["detail_json"] == canonical({"manifest_sha256": row["manifest_sha256"], "summary": summary, "processing_authorized": False}), "EVENT_READBACK")
    result.update(durable_state="COMPLETE_PREPARED", complete_preparation_verified=True,
        manifest_sha256=row["manifest_sha256"], created_at=row["created_at"], summary=summary,
        inventory_sha256=manifest["inventory_sha256"], evidence_sha256=manifest["evidence_sha256"])
    return result


def emit(result):
    for key in ("receipt_count", "plan_count", "batch_count", "event_count", "complete_preparation_verified", "durable_state"):
        v = result[key]
        print("RECOVERY_READBACK_" + key.upper() + "=" + str(int(v) if isinstance(v, bool) else v), flush=True)
    for n, r in enumerate(result["receipts"], 1):
        for key in ("receipt_id", "query_sha256", "boundary_count", "considered_count", "matched_count", "content_available_count",
                    "metadata_only_count", "governed_hold_count", "created_at"):
            print(f"RECOVERY_READBACK_Q{n}_{key.upper()}={r[key]}", flush=True)
    if result["complete_preparation_verified"]:
        for key in ("manifest_sha256", "created_at", "inventory_sha256", "evidence_sha256"):
            print("RECOVERY_READBACK_" + key.upper() + "=" + result[key], flush=True)
        # Do not print raw dynamic keys or values from a private manifest.
        print("RECOVERY_READBACK_PREPARED_SOURCES=8404", flush=True)
        print("RECOVERY_READBACK_AVAILABILITY_EXCEPTIONS=5", flush=True)
        for name in ("EXACT_COMPLETE_EMPTY_TEXT", "BROAD_COMPLETE_MATCH_OUTSIDE_EXTRACTION_STATUS", "NOT_COUNTED_BY_LEGACY_PREDICATE"):
            print("RECOVERY_READBACK_CONDITION_" + name + "=" + str(result["summary"]["availability_candidate_conditions"].get(name, 0)), flush=True)
    print("RECOVERY_READBACK_DATABASE_WRITES=0", flush=True)
    print("RECOVERY_READBACK_NEW_SEARCH_RECEIPTS=0", flush=True)
    print("RECOVERY_READBACK_ORIGINAL_TASK_REPLAYED=0", flush=True)
    print("RECOVERY_READBACK_COMPLETE=1", flush=True)


def main():
    if os.getenv("SALUS_DB_BACKEND", "").lower() != "postgres":
        raise SystemExit("Managed PostgreSQL required")
    from database import connect_database
    conn = None
    try:
        conn = connect_database()
        result = reconcile(conn)
        conn.close()
        conn = connect_database()
        require(reconcile(conn) == result, "INDEPENDENT_READBACK_CHANGED")
        emit(result)
    except Exception:
        # Unknown SQL/JSON/driver messages may contain source data; emit stage only.
        print("RECOVERY_READBACK_FAILURE_STAGE=" + STAGE, flush=True)
        raise SystemExit(1) from None
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
