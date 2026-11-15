"""Task-bound, aggregate-only Knowledge consideration and durable receipt proof."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from salcapa_knowledge_consideration import consider


TASK_KEY = "salus-representation-gap-reconciliation-20261115"
ACTOR = "System Administrator - task consideration " + TASK_KEY
STAGE = "not_started"
CREATED_RECEIPTS = 0
QUERIES = (
    ("coverage_reconciliation", "source inventory representation gap provenance reconciliation completeness"),
    ("durable_intake", "durable intake metadata ledger concurrency audit checkpoint recovery"),
    ("safe_processing", "governed extraction review processor remediation retry paused source hold"),
    ("stable_census", "stable census source version query receipt verification cleanup"),
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


# Only scalar metadata leaves SQL; extracted text and free-text errors are not selected.
KNOWN_CODES = frozenset(["DOCUMENT_ACTIVE_CONTENT","DOCUMENT_ACTIVE_OR_LEGACY_FORMAT","DOCUMENT_PACKAGE_INVALID","DOCUMENT_XML_INVALID","FORMAT_NOT_SUPPORTED","IMAGE_FORMAT_MISMATCH","IMAGE_HEADER_INVALID","MEDIA_FORMAT_MISMATCH","MEDIA_HEADER_INVALID","MEDIA_STREAM_INVALID","MEDIA_STREAM_LIMIT","PDF_ACTIVE_CONTENT","PDF_ENCRYPTED","PDF_HEADER_INVALID","PDF_PAGE_LIMIT","PDF_PARSE_FAILED","TEXT_ENCODING_UNSUPPORTED","DOCUMENT_EXPANSION_LIMIT","IMAGE_METADATA_LIMIT","IMAGE_RESOURCE_LIMIT","MEDIA_RESOURCE_LIMIT","OCR_RESOURCE_LIMIT","PDF_PAGE_CONTENT_LIMIT","PDF_RESOURCE_LIMIT","PDF_SOURCE_LIMIT","TRANSCRIPT_OUTPUT_INVALID","TRANSCRIPTION_CAPACITY_UNAVAILABLE","TRANSCRIPTION_FAILED"])
CATEGORIES = ("governed_hold", "governed_review", "retry_paused", "automatic_retry",
              "complete_without_text", "no_candidate", "other_or_conflicting")

def unresolved_snapshot(conn):
    """Reconcile the exact service availability predicate to source-correlated metadata."""
    def field(path):
        if getattr(conn, "backend", "sqlite") == "postgres":
            return "COALESCE(c.classification_json::jsonb #>> '{" + path + "}','')"
        return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"
    rows = conn.execute(
        "SELECT c.source_item_id,c.id,c.source_sha256,c.source_archive_item_id,"
        + field("extraction,status") + " extraction_status,"
        + field("extraction,failure_code") + " failure_code,"
        + "CASE WHEN LENGTH(TRIM(" + field("extraction,text") + "))>0 THEN 1 ELSE 0 END has_text,"
        + "CASE WHEN c.classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END legacy_complete "
        + "FROM m365_knowledge_candidates c ORDER BY c.id"
    ).fetchall()
    represented = represented_ids(conn)
    holds = {str(r["source_item_id"]) for r in conn.execute(
        "SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'").fetchall()}
    by_source = {}
    fingerprints = []
    legacy_content, actual_content = set(), set()
    for row in rows:
        source = str(row["source_item_id"])
        if source not in represented:
            raise RuntimeError("Candidate representation left the live union")
        by_source.setdefault(source, []).append(row)
        if row["legacy_complete"]:
            legacy_content.add(source)
        if row["extraction_status"] == "Complete" and row["has_text"]:
            actual_content.add(source)
        fingerprints.append((source, row["id"], row["source_sha256"], row["source_archive_item_id"],
                             row["extraction_status"], row["failure_code"], row["has_text"], row["legacy_complete"]))
    unresolved = represented - legacy_content
    if len(represented) > 100000 or len(rows) > 150000:
        raise RuntimeError("Recovery census resource bound exceeded")
    counts = {key: 0 for key in CATEGORIES}
    codes = {code: 0 for code in sorted(KNOWN_CODES)}
    codes.update({"EMPTY": 0, "OTHER_REQUIRES_CHARACTERIZATION": 0})
    archive_missing = multiple_candidates = unknown_code_rows = 0
    for source in unresolved:
        candidates = by_source.get(source, [])
        statuses = {str(r["extraction_status"]) for r in candidates}
        if source in holds:
            category = "governed_hold"
        elif len(statuses) > 1:
            category = "other_or_conflicting"
        elif statuses == {"Review Required"}:
            category = "governed_review"
        elif statuses == {"Retry Paused"}:
            category = "retry_paused"
        elif statuses == {"Automatic Retry Required"}:
            category = "automatic_retry"
        elif statuses == {"Complete"}:
            category = "complete_without_text"
        elif not candidates:
            category = "no_candidate"
        else:
            category = "other_or_conflicting"
        counts[category] += 1
        multiple_candidates += int(len(candidates) > 1)
        archive_missing += int(bool(candidates) and not any(r["source_archive_item_id"] for r in candidates))
        # Code counts are candidate-row counts; never add these to distinct-source counts.
        for row in candidates:
            code = str(row["failure_code"])
            key = code if code in KNOWN_CODES else ("EMPTY" if not code else "OTHER_REQUIRES_CHARACTERIZATION")
            codes[key] += 1
            unknown_code_rows += int(key == "OTHER_REQUIRES_CHARACTERIZATION")
    if sum(counts.values()) != len(unresolved):
        raise RuntimeError("Recovery categories do not partition the unresolved sources")
    fingerprint = hashlib.sha256(json.dumps(
        {"represented": sorted(represented), "holds": sorted(holds), "candidates": fingerprints},
        sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {
        "represented_files": len(represented),
        "service_content_available_files": len(legacy_content),
        "metadata_only_or_unresolved_files": len(unresolved),
        "exact_complete_with_nonempty_text_files": len(actual_content),
        "service_complete_without_verified_text_files": len(legacy_content - actual_content),
        "text_complete_not_counted_by_service_files": len(actual_content - legacy_content),
        "unresolved_with_multiple_candidates": multiple_candidates,
        "unresolved_without_recorded_archive": archive_missing,
        "unknown_failure_code_candidate_rows": unknown_code_rows,
        "categories": counts, "failure_code_candidate_rows": codes,
        "snapshot_sha256": fingerprint,
    }

AREA_CODES = {
    "10 Pending Classification": "PENDING",
    "20 Ready for Intake Review": "READY_REVIEW",
    "30 Exceptions and Manual Review": "EXCEPTIONS",
    "40 Customer Batch Staging - Unassigned": "CUSTOMER_STAGING",
    "90 Migration Hold": "MIGRATION_HOLD",
    "90 Processed Intake": "PROCESSED",
    "Does Not Upload": "DOES_NOT_UPLOAD",
}
MAX_ENROLLMENT = 116
PARKED_STATUS = "Assignment Required"
PARKED_REASON = "source_representation_reconciliation_review_required"
PREVIOUS_ACTOR = "System Administrator - task consideration salus-unresolved-recovery-census-20261115"

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)

def scoped_inventory(intake):
    """Full root delta metadata census, with exact folder ancestry; no /content request."""
    root_id, drive = intake.config.folder_item_id, intake.config.drive_id
    base = f"https://graph.microsoft.com/v1.0/drives/{drive}/items/{root_id}"
    response = intake.client.get(base, headers=intake._headers(),
        params={"$select": "id,name,folder,remoteItem"})
    if response.status_code != 200:
        raise RuntimeError("Root metadata unavailable")
    root = response.json()
    if (root.get("id") != root_id or root.get("name") != "SalCAPA Intake"
            or not isinstance(root.get("folder"), dict) or "remoteItem" in root):
        raise RuntimeError("Root boundary mismatch")
    endpoint = base + "/delta"
    page, params, visited, items = endpoint, {"$select":
        "id,name,size,file,folder,remoteItem,deleted,eTag,cTag,lastModifiedDateTime,parentReference,createdBy,lastModifiedBy,webUrl",
        "$top": "200"}, set(), {}
    while page:
        if page in visited or len(visited) >= 2000:
            raise RuntimeError("Inventory pagination bound")
        visited.add(page)
        response = intake.client.get(page, headers=intake._headers(), params=params)
        if response.status_code != 200:
            raise RuntimeError("Inventory page unavailable")
        payload = response.json()
        values = payload.get("value")
        next_link, delta_link = payload.get("@odata.nextLink"), payload.get("@odata.deltaLink")
        if not isinstance(values, list) or len(values) > 1000 or bool(next_link) == bool(delta_link):
            raise RuntimeError("Inventory page incomplete")
        link = next_link or delta_link
        parsed, expected = urlparse(str(link)), urlparse(endpoint)
        if (not isinstance(link, str) or len(link) > 8192 or parsed.scheme != "https"
                or parsed.netloc != "graph.microsoft.com" or parsed.path != expected.path
                or not parsed.query or parsed.fragment):
            raise RuntimeError("Inventory continuation left boundary")
        for item in values:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", str(item.get("id", ""))):
                raise RuntimeError("Inventory identity invalid")
            key = item["id"]
            if "deleted" in item:
                items.pop(key, None)
                continue
            if "remoteItem" in item:
                raise RuntimeError("Inventory shortcut rejected")
            if key == root_id:
                if not isinstance(item.get("folder"), dict):
                    raise RuntimeError("Inventory root type changed")
                continue
            parent = item.get("parentReference") or {}
            if parent.get("driveId") not in (None, "", drive):
                raise RuntimeError("Inventory drive mismatch")
            if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", str(parent.get("id", ""))):
                raise RuntimeError("Inventory parent invalid")
            name = item.get("name")
            if (not isinstance(name, str) or not name or name in (".", "..")
                    or "/" in name or "\\" in name or len(name) > 512):
                raise RuntimeError("Inventory name invalid")
            file, folder = isinstance(item.get("file"), dict), isinstance(item.get("folder"), dict)
            if file == folder:
                raise RuntimeError("Inventory type invalid")
            if file:
                if (not isinstance(item.get("size"), int) or isinstance(item["size"], bool)
                        or item["size"] < 0 or not item.get("eTag") or not item.get("lastModifiedDateTime")):
                    raise RuntimeError("Inventory provenance incomplete")
            items[key] = item
            if len(items) > 100000:
                raise RuntimeError("Inventory item bound")
        page, params = next_link, None
    top_items = [(key,item) for key,item in items.items() if item["parentReference"]["id"] == root_id]
    tops = {item["name"]: key for key,item in top_items}
    if set(tops) != set(AREA_CODES) or len(top_items) != 7:
        raise RuntimeError("Inventory top-level boundary changed")
    if any(not isinstance(items[key].get("folder"), dict) for key in tops.values()):
        raise RuntimeError("Inventory top-level type changed")
    files = {}
    for key, item in items.items():
        if not isinstance(item.get("file"), dict):
            continue
        path, seen, current = [item["name"]], {key}, item["parentReference"]["id"]
        while current != root_id:
            if current in seen or current not in items or len(seen) > 1000:
                raise RuntimeError("Inventory ancestry invalid")
            seen.add(current)
            folder = items[current]
            if not isinstance(folder.get("folder"), dict):
                raise RuntimeError("Inventory ancestor not folder")
            path.append(folder["name"])
            if folder["parentReference"]["id"] == root_id:
                area, area_id = folder["name"], current
            current = folder["parentReference"]["id"]
        if len(path) < 2 or path[-1] not in AREA_CODES:
            raise RuntimeError("Inventory file outside source areas")
        owner, owner_id = intake._identity(item.get("createdBy"))
        metadata = {
            "relative_path": "/".join(reversed(path)),
            "mime_type": str(item["file"].get("mimeType", ""))[:255],
            "last_modified": str(item["lastModifiedDateTime"]),
            "ctag": str(item.get("cTag", "")),
            "source_owner": owner, "source_owner_id": owner_id,
            "last_modified_by": intake._identity(item.get("lastModifiedBy"))[0],
            "web_url": intake._trusted_source_url(item.get("webUrl")),
            "governed_source_area": area, "source_area_id": area_id, "source_root_id": root_id,
            "representation_only": True, "processing_authorized": False,
        }
        files[key] = {"item_id": key, "area_id": area_id, "area": area,
            "parent_id": item["parentReference"]["id"], "name": item["name"],
            "etag": str(item["eTag"]), "size": item["size"], "metadata_json": canonical(metadata)}
    return files

def coverage_plan(conn, inventory, *, emit=False):
    missing = sorted(set(inventory) - represented_ids(conn))
    if emit:
        print(f"GAP_CURRENT_SOURCE_FILES={len(inventory)}", flush=True)
        print(f"GAP_MISSING_CURRENT_SOURCE_FILES={len(missing)}", flush=True)
        for area, code in AREA_CODES.items():
            print(f"GAP_MISSING_AREA_{code}={sum(inventory[k]['area'] == area for k in missing)}", flush=True)
    if len(missing) > MAX_ENROLLMENT:
        raise RuntimeError("Current gap exceeds the approved 116-item intervention cap")
    return {key: inventory[key] for key in missing}

def audit_tables(conn):
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS m365_knowledge_representation_batches (
        operation_key TEXT PRIMARY KEY, batch_id TEXT NOT NULL UNIQUE,
        source_drive_id TEXT NOT NULL, source_root_id TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, item_count INTEGER NOT NULL,
        actor TEXT NOT NULL, created_at TEXT NOT NULL
      );
      CREATE TABLE IF NOT EXISTS m365_knowledge_representation_events (
        operation_key TEXT NOT NULL, source_item_id TEXT NOT NULL,
        event_type TEXT NOT NULL, detail_json TEXT NOT NULL,
        PRIMARY KEY(operation_key,source_item_id)
      );
    """)
    conn.commit()

def enroll_missing(conn, inventory, plan, drive, root, timestamp):
    """Insert only absent parked metadata, with a per-item audit and atomic batch."""
    audit_tables(conn)
    try:
        if getattr(conn, "backend", "sqlite") == "postgres":
            conn.execute("SET LOCAL lock_timeout='3s'")
            conn.execute("LOCK TABLE m365_knowledge_candidates,m365_knowledge_holds,m365_bulk_items IN SHARE ROW EXCLUSIVE MODE")
        else:
            conn.execute("BEGIN IMMEDIATE")
        if conn.execute("SELECT COUNT(*) FROM m365_knowledge_representation_batches WHERE operation_key=?",
                        (TASK_KEY,)).fetchone()[0]:
            raise RuntimeError("Operation already recorded; reconcile its durable result")
        if coverage_plan(conn, inventory) != plan:
            raise RuntimeError("Representation membership changed before enrollment")
        manifest_sha = hashlib.sha256(canonical({"drive_id":drive,"root_id":root,"items":plan}).encode()).hexdigest()
        batch_id = __import__("uuid").uuid4().hex
        conn.execute("INSERT INTO m365_knowledge_representation_batches VALUES(?,?,?,?,?,?,?,?)",
            (TASK_KEY, batch_id, drive, root, manifest_sha, len(plan), ACTOR, timestamp))
        for key, item in sorted(plan.items()):
            # The legacy pending_id column is a scope key. Use the verified root,
            # distinct from the scheduled Pending cursor, so normal delta discovery
            # cannot overwrite/re-enable these parked inventory rows.
            updated = conn.execute("""
              INSERT INTO m365_bulk_items
              (drive_id,pending_id,item_id,parent_id,name,kind,etag,size,metadata_json,
               status,reason,attempts,next_attempt,updated_at,seen_generation,lease_owner,lease_until)
              VALUES(?,?,?,?,?,'file',?,?,?,?,?,0,0,?,0,'',0)
              ON CONFLICT(drive_id,pending_id,item_id) DO NOTHING
            """, (drive,root,key,item["parent_id"],item["name"],item["etag"],
                  item["size"],item["metadata_json"],PARKED_STATUS,PARKED_REASON,
                  int(datetime.fromisoformat(timestamp).timestamp())))
            if updated.rowcount != 1:
                raise RuntimeError("Existing or removed work row conflicts; preserve and review")
            conn.execute("INSERT INTO m365_knowledge_representation_events VALUES(?,?,?,?)",
                (TASK_KEY,key,"MissingSourceMetadataRepresentedForGovernedReview",canonical(item)))
        if set(inventory) - represented_ids(conn):
            raise RuntimeError("Representation gap remains inside enrollment transaction")
        conn.commit()
        return {"batch_id":batch_id,"manifest_sha256":manifest_sha,"item_count":len(plan),"created_at":timestamp}
    except Exception:
        conn.rollback()
        raise

def verify_enrollment(conn, plan, drive, root, expected):
    batch = conn.execute("SELECT * FROM m365_knowledge_representation_batches WHERE operation_key=?",
                         (TASK_KEY,)).fetchone()
    manifest_sha = hashlib.sha256(canonical({"drive_id":drive,"root_id":root,"items":plan}).encode()).hexdigest()
    if (batch is None or batch["manifest_sha256"] != manifest_sha
            or batch["batch_id"] != expected["batch_id"] or batch["item_count"] != len(plan)
            or batch["source_drive_id"] != drive or batch["source_root_id"] != root
            or batch["created_at"] != expected["created_at"]
            or expected["item_count"] != len(plan)
            or batch["actor"] != ACTOR or expected["manifest_sha256"] != manifest_sha):
        raise RuntimeError("Durable enrollment batch disagrees")
    events = conn.execute("SELECT source_item_id,event_type,detail_json FROM m365_knowledge_representation_events WHERE operation_key=?",
                          (TASK_KEY,)).fetchall()
    if {str(row["source_item_id"]): (row["event_type"],row["detail_json"]) for row in events} != {
            key: ("MissingSourceMetadataRepresentedForGovernedReview",canonical(item)) for key,item in plan.items()}:
        raise RuntimeError("Durable enrollment events disagree")
    for key,item in plan.items():
        row = conn.execute("SELECT * FROM m365_bulk_items WHERE drive_id=? AND pending_id=? AND item_id=?",
                           (drive,root,key)).fetchone()
        expected_fields = {"parent_id":item["parent_id"],"name":item["name"],"kind":"file",
            "etag":item["etag"],"size":item["size"],"metadata_json":item["metadata_json"],
            "status":PARKED_STATUS,"reason":PARKED_REASON,"attempts":0,"next_attempt":0,
            "seen_generation":0,"lease_owner":"","lease_until":0}
        if row is None or any(row[k] != v for k,v in expected_fields.items()):
            raise RuntimeError("Durable parked representation disagrees")

def assert_no_task_receipts(conn):
    for actor, label in ((PREVIOUS_ACTOR,"PRIOR_CENSUS"),(ACTOR,"THIS_OPERATION")):
        count = int(conn.execute("SELECT COUNT(*) FROM m365_knowledge_consideration_receipts WHERE actor LIKE ?",
                                (actor + " / %",)).fetchone()[0])
        print(f"GAP_{label}_DURABLE_TASK_RECEIPTS={count}", flush=True)
        if count:
            raise RuntimeError("Existing task receipts require reconciliation before another search")

def main():
    global STAGE
    if os.getenv("SALUS_DB_BACKEND","").lower() != "postgres":
        raise RuntimeError("Managed PostgreSQL required")
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake
    conn, intake, batch = None, None, None
    try:
        STAGE = "prior_receipt_readback"
        conn = connect_database()
        assert_no_task_receipts(conn)
        if conn.execute("SELECT to_regclass('m365_knowledge_representation_batches')").fetchone()[0]:
            if conn.execute("SELECT COUNT(*) FROM m365_knowledge_representation_batches WHERE operation_key=?",
                            (TASK_KEY,)).fetchone()[0]:
                raise RuntimeError("Operation already has a durable batch")
        conn.close()
        conn = None
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        STAGE = "initial_source_inventory"
        inventory = scoped_inventory(intake)
        if len(inventory) < 22447:
            raise RuntimeError("Source boundary below accepted minimum")
        conn = connect_database()
        plan = coverage_plan(conn, inventory, emit=True)
        conn.close()
        conn = None
        STAGE = "stable_source_prewrite"
        if scoped_inventory(intake) != inventory:
            raise RuntimeError("Source versions or metadata changed; no enrollment")
        STAGE = "atomic_metadata_enrollment"
        conn = connect_database()
        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        batch = enroll_missing(conn, inventory, plan, intake.config.drive_id, intake.config.folder_item_id, timestamp)
        print(f"GAP_COMMITTED_BATCH_ID={batch['batch_id']}", flush=True)
        print(f"GAP_COMMITTED_METADATA_ROWS={batch['item_count']}", flush=True)
        print(f"GAP_MANIFEST_SHA256={batch['manifest_sha256']}", flush=True)
        conn.close()
        conn = None
        STAGE = "fresh_durable_enrollment_readback"
        conn = connect_database()
        verify_enrollment(conn, plan, intake.config.drive_id, intake.config.folder_item_id, batch)
        if set(inventory) - represented_ids(conn):
            raise RuntimeError("Current source membership no longer represented")
        print("GAP_ENROLLMENT_DURABLE_READBACK=1", flush=True)
        print("GAP_MISSING_CURRENT_SOURCE_FILES_AFTER=0", flush=True)
        before = unresolved_snapshot(conn)
        # Each search census also checks the complete metadata inventory against
        # the pre-enrollment source version/ancestry snapshot.
        def stable_source():
            if scoped_inventory(intake) != inventory:
                raise RuntimeError("Source version/ancestry changed after enrollment")
            return {key: value["etag"] for key,value in inventory.items()}
        STAGE = "stable_census_and_task_receipts"
        summaries = run_search(conn, source_census_fn=stable_source,
                               minimum_boundary=22447, minimum_represented=22457)
        STAGE = "recovery_metadata_readback"
        after = unresolved_snapshot(conn)
        if before != after:
            raise RuntimeError("Recovery metadata changed during search")
        if any(s["metadata_only_or_unresolved_files"] != after["metadata_only_or_unresolved_files"]
               or s["content_available_files"] != after["service_content_available_files"] for s in summaries):
            raise RuntimeError("Recovery counts disagree with durable search receipts")
        for key,value in after.items():
            if isinstance(value,dict):
                for label,count in sorted(value.items()):
                    print(f"RECOVERY_{key.upper()}_{label.upper()}={count}", flush=True)
            else:
                print(f"RECOVERY_{key.upper()}={value}", flush=True)
        print("RECOVERY_METADATA_STABLE=1", flush=True)
        print("GAP_SOURCE_CONTENT_DOWNLOADS=0", flush=True)
        print("GAP_AUTOMATIC_PROCESSING_ENABLED=0", flush=True)
        print("GAP_PROTECTED_MEMBER_ACCESS=0", flush=True)
        print("GAP_ASSIGNMENT_OR_RELEASE_AUTHORITY=0", flush=True)
        print("GAP_RECONCILIATION_COMPLETE=1", flush=True)
        print("RECOVERY_ALL_CONTENT_RESOLVED=0", flush=True)
    except Exception as exc:
        print(f"GAP_FAILURE_TYPE={type(exc).__name__}", flush=True)
        print(f"GAP_FAILURE_STAGE={STAGE}", flush=True)
        print(f"GAP_NEW_TASK_RECEIPTS_CREATED={CREATED_RECEIPTS}", flush=True)
        print(f"GAP_COMMITTED_BATCH_PRESENT={int(batch is not None)}", flush=True)
        # A committed metadata batch is retained for durable reconciliation even
        # if later source drift prevents global census acceptance.
        raise SystemExit(1) from None
    finally:
        if conn is not None:
            conn.close()
        if intake is not None:
            intake.client.close()
            intake.credential.close()

if __name__ == "__main__":
    main()
