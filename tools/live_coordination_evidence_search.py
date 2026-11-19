"""Task-bound, aggregate-only Knowledge consideration and durable receipt proof."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from salcapa_knowledge_consideration import consider


TASK_KEY = "coordination-evidence-review-20261118"
ACTOR = "System Administrator - task consideration " + TASK_KEY
STAGE = "not_started"
CREATED_RECEIPTS = 0
QUERIES = (
    ("responder_handoff", "liaison command transfer briefing acknowledgement responsibility communications interoperability"),
    ("public_warnings", "warning alert accessibility comprehension language accountability evacuation shelter"),
    ("family_reunification", "reunification custody caregiver guardian verification family assistance supervision privacy"),
    ("recovery_and_review", "reentry re-entry reopening repopulation debrief improvement corrective-action evidence evaluation"),
)


def source_census(intake):
    """Read scoped Graph metadata only; do not touch cursors, source bytes or work rows."""
    config = intake.config
    base = f"https://graph.microsoft.com/v1.0/drives/{config.drive_id}/items/{config.folder_item_id}"
    root = intake.client.get(base, headers=intake._headers(),
        params={"$select": "id,name,folder,remoteItem"})
    if root.status_code != 200:
        raise RuntimeError("Source root could not be verified")
    payload = root.json()
    if (payload.get("id") != config.folder_item_id or payload.get("name") != "SalCAPA Intake"
            or "folder" not in payload or "remoteItem" in payload):
        raise RuntimeError("Source root does not match the authorized boundary")
    endpoint = base + "/delta"
    page, params = endpoint, {"$select": "id,file,folder,remoteItem,deleted,eTag,lastModifiedDateTime,parentReference", "$top": "200"}
    visited, files = set(), {}
    while page:
        if page in visited or len(visited) >= 2000:
            raise RuntimeError("Source census pagination did not terminate")
        visited.add(page)
        response = intake.client.get(page, headers=intake._headers(), params=params)
        if response.status_code != 200:
            raise RuntimeError("Source census page was unavailable")
        payload = response.json()
        values = payload.get("value")
        next_link, delta_link = payload.get("@odata.nextLink"), payload.get("@odata.deltaLink")
        if (not isinstance(values, list) or len(values) > 1000
                or bool(next_link) == bool(delta_link)):
            raise RuntimeError("Source census page was incomplete")
        continuation = next_link or delta_link
        if not isinstance(continuation, str) or len(continuation) > 8192:
            raise RuntimeError("Source census continuation was invalid")
        parsed, expected = urlparse(continuation), urlparse(endpoint)
        if (parsed.scheme != "https" or parsed.netloc != "graph.microsoft.com"
                or parsed.path != expected.path or not parsed.query or parsed.fragment):
            raise RuntimeError("Source census continuation left the authorized boundary")
        for item in values:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", str(item.get("id", ""))):
                raise RuntimeError("Source census identity was invalid")
            identity = item["id"]
            if "deleted" in item:
                files.pop(identity, None)
                continue
            if "remoteItem" in item:
                raise RuntimeError("Source census encountered a remote shortcut")
            drive = (item.get("parentReference") or {}).get("driveId")
            if drive and drive != config.drive_id:
                raise RuntimeError("Source census item left the authorized drive")
            if "file" in item:
                if not item.get("eTag") or not item.get("lastModifiedDateTime"):
                    raise RuntimeError("Source census version was unavailable")
                files[identity] = (str(item["eTag"]), str(item["lastModifiedDateTime"]))
            elif "folder" not in item:
                raise RuntimeError("Source census item type was unsupported")
            if len(files) > 100000:
                raise RuntimeError("Source census exceeded its explicit resource bound")
        page, params = next_link, None
    return files


def represented_ids(conn):
    return {str(row["source_item_id"]) for row in conn.execute("""
        SELECT source_item_id FROM m365_knowledge_candidates
        UNION SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
        UNION SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
    """).fetchall()}


def snapshot(conn):
    current = {str(row["source_item_id"]) for row in conn.execute(
        "SELECT DISTINCT item_id source_item_id FROM m365_bulk_items "
        "WHERE kind='file' AND status<>'Removed'"
    ).fetchall()}
    represented = represented_ids(conn)
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


def run_search(conn, *, source_census_fn, minimum_boundary=1, minimum_represented=22399,
               queries=QUERIES, consider_fn=consider):
    global STAGE, CREATED_RECEIPTS
    CREATED_RECEIPTS = 0
    STAGE = "represented_precheck"
    pre = snapshot(conn)
    bulk_rows, represented, _digest = pre
    print(f"TASK_KNOWLEDGE_PRECHECK_ACTIVE_BULK_FILES={bulk_rows}", flush=True)
    print(f"TASK_KNOWLEDGE_PRECHECK_REPRESENTED_FILES={represented}", flush=True)
    print(f"TASK_KNOWLEDGE_LEDGER_MEMBERSHIP_SHA256={pre[2]}", flush=True)
    if represented < minimum_represented:
        raise RuntimeError("Live representation count is below the governed minimum")
    STAGE = "duplicate_receipt_precheck"
    if conn.execute(
        "SELECT COUNT(*) count FROM m365_knowledge_consideration_receipts WHERE actor LIKE ?",
        (ACTOR + " / %",),
    ).fetchone()["count"]:
        raise RuntimeError("This task already has receipts; do not blindly repeat it")
    STAGE = "source_census"
    sources = source_census_fn()
    boundary = len(sources)
    missing = len(set(sources) - represented_ids(conn))
    print(f"TASK_KNOWLEDGE_PRECHECK_BOUNDARY_FILES={boundary}", flush=True)
    print(f"TASK_KNOWLEDGE_UNREPRESENTED_CURRENT_SOURCE_FILES={missing}", flush=True)
    census_hash = hashlib.sha256(json.dumps(sources, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    print(f"TASK_KNOWLEDGE_SOURCE_CENSUS_SHA256={census_hash}", flush=True)
    if boundary < minimum_boundary or represented < boundary or missing:
        raise RuntimeError("Actual source inventory is not fully represented")
    previous = os.environ.get("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES")
    summaries = []
    try:
        # The approved service accepts its boundary through this variable. Bind it
        # to the observed live source ledger, rather than a historical constant.
        os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = str(boundary)
        for number, (label, query) in enumerate(queries, 1):
            STAGE = "membership_prequery"
            if snapshot(conn) != pre:
                raise RuntimeError("Source membership changed during task consideration")
            actor = ACTOR + " / " + label
            created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
            STAGE = "create_receipt"
            result = consider_fn(conn, query, actor, created_at)
            CREATED_RECEIPTS += 1
            STAGE = "verify_durable_receipt"
            coverage = verify_receipt(conn, result, query, actor, created_at, boundary, represented)
            STAGE = "membership_postquery"
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
        STAGE = "source_census_readback"
        if source_census_fn() != sources:
            raise RuntimeError("Actual source membership or versions changed")
    finally:
        if previous is None:
            os.environ.pop("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES", None)
        else:
            os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = previous
    print(f"TASK_KNOWLEDGE_VERIFIED_RECEIPTS={len(summaries)}", flush=True)
    print("TASK_KNOWLEDGE_SOURCE_MEMBERSHIP_STABLE=1", flush=True)
    print("TASK_KNOWLEDGE_SOURCE_CENSUS_STABLE=1", flush=True)
    print("TASK_KNOWLEDGE_PROTECTED_MEMBER_ACCESS=0", flush=True)
    print("TASK_KNOWLEDGE_ASSIGNMENT_OR_RELEASE_AUTHORITY=0", flush=True)
    print("TASK_KNOWLEDGE_COMPLETE=1", flush=True)
    return summaries


def main():
    global STAGE
    if os.getenv("SALUS_DB_BACKEND", "").lower() != "postgres":
        raise RuntimeError("Managed PostgreSQL is required")
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake
    STAGE = "connect_database"
    conn = connect_database()
    intake = None
    try:
        STAGE = "initialize_scoped_source_client"
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        run_search(conn, source_census_fn=lambda: source_census(intake))
    except Exception as exc:
        # Do not emit database values, source names, paths, contents or exception
        # details into telemetry. A partial receipt is not a complete task run.
        print(f"TASK_KNOWLEDGE_FAILURE_TYPE={type(exc).__name__}", flush=True)
        print(f"TASK_KNOWLEDGE_FAILURE_STAGE={STAGE}", flush=True)
        print(f"TASK_KNOWLEDGE_NEW_RECEIPTS_CREATED={CREATED_RECEIPTS}", flush=True)
        raise SystemExit(1) from None
    finally:
        if intake is not None:
            intake.client.close()
            intake.credential.close()
        conn.close()


if __name__ == "__main__":
    main()
