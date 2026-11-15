"""Task-bound, aggregate-only Knowledge consideration and durable receipt proof."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from salcapa_knowledge_consideration import consider


TASK_KEY = "salus-stable-census-diagnostics-20261115"
ACTOR = "System Administrator - task consideration " + TASK_KEY
STAGE = "not_started"
CREATED_RECEIPTS = 0
QUERIES = (
    ("inventory_integrity", "source inventory stable census provenance version metadata integrity"),
    ("failure_diagnosis", "inventory verification failure pagination ancestry request diagnostics"),
    ("recovery_controls", "extraction review processor remediation retry paused governed hold"),
    ("coverage_proof", "complete corpus consideration receipt audit stable membership cleanup"),
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
                       "bounded_candidate_results": len(result["results"]),
                       "receipt_actor": actor, "receipt_created_at": created_at}
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
MAX_OBSERVATIONS = 3

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


FAILURE_CODES = frozenset(["ROOT_BOUNDARY_MISMATCH","PAGINATION_BOUND_EXCEEDED","PAGE_SHAPE_INVALID","CONTINUATION_SCOPE_INVALID","ITEM_ID_INVALID","SHORTCUT_REJECTED","ROOT_TYPE_CHANGED","DRIVE_MISMATCH","PARENT_ID_INVALID","NAME_INVALID","ITEM_TYPE_INVALID","SOURCE_PROVENANCE_INCOMPLETE","ITEM_BOUND_EXCEEDED","TOP_LEVEL_BOUNDARY_CHANGED","TOP_LEVEL_TYPE_CHANGED","ANCESTRY_INVALID","ANCESTOR_NOT_FOLDER","SOURCE_AREA_INVALID","ROOT_REQUEST_FAILED","PAGE_REQUEST_FAILED","ROOT_JSON_INVALID","PAGE_JSON_INVALID","ROOT_PAYLOAD_INVALID","PAGE_PAYLOAD_INVALID","METADATA_HELPER_REJECTED","DIFF_INPUT_INVALID","STABILITY_NOT_ESTABLISHED","SOURCE_CHANGED_DURING_SEARCH","MISSING_REPRESENTATION","BOUNDARY_BELOW_MINIMUM","PRIOR_TASK_RECEIPTS_PRESENT","PRIOR_ENROLLMENT_BATCH_PRESENT","RECOVERY_METADATA_CHANGED","RECOVERY_RECEIPT_DISAGREEMENT","UNEXPECTED_FAILURE","ROOT_HTTP_BAD_REQUEST","ROOT_HTTP_UNAUTHORIZED","ROOT_HTTP_FORBIDDEN","ROOT_HTTP_NOT_FOUND","ROOT_HTTP_THROTTLED","ROOT_HTTP_RESYNC_REQUIRED","ROOT_HTTP_SERVER_ERROR","ROOT_HTTP_OTHER","PAGE_HTTP_BAD_REQUEST","PAGE_HTTP_UNAUTHORIZED","PAGE_HTTP_FORBIDDEN","PAGE_HTTP_NOT_FOUND","PAGE_HTTP_THROTTLED","PAGE_HTTP_RESYNC_REQUIRED","PAGE_HTTP_SERVER_ERROR","PAGE_HTTP_OTHER"])
INVENTORY_ATTEMPTS = 0
INVENTORIES_COMPLETED = 0

class CensusFailure(RuntimeError):
    def __init__(self, code):
        self.code = code if isinstance(code,str) and code in FAILURE_CODES else "UNEXPECTED_FAILURE"
        super().__init__(self.code)

def request_metadata(intake, url, params, phase):
    if phase not in ("ROOT","PAGE"):
        raise CensusFailure("UNEXPECTED_FAILURE")
    try:
        response = intake.client.get(url, headers=intake._headers(), params=params)
    except Exception:
        raise CensusFailure(phase + "_REQUEST_FAILED") from None
    status = getattr(response,"status_code",0)
    if not isinstance(status,int) or isinstance(status,bool):
        status = 0
    if status != 200:
        suffix = {400:"HTTP_BAD_REQUEST",401:"HTTP_UNAUTHORIZED",403:"HTTP_FORBIDDEN",
                  404:"HTTP_NOT_FOUND",410:"HTTP_RESYNC_REQUIRED",429:"HTTP_THROTTLED"}.get(status)
        if suffix is None:
            suffix = "HTTP_SERVER_ERROR" if isinstance(status,int) and 500 <= status <= 599 else "HTTP_OTHER"
        raise CensusFailure(phase + "_" + suffix)
    try:
        payload = response.json()
    except Exception:
        raise CensusFailure(phase + "_JSON_INVALID") from None
    if not isinstance(payload,dict):
        raise CensusFailure(phase + "_PAYLOAD_INVALID")
    return payload


def scoped_inventory(intake):
    """Full root delta metadata census, with exact folder ancestry; no /content request."""
    root_id, drive = intake.config.folder_item_id, intake.config.drive_id
    base = f"https://graph.microsoft.com/v1.0/drives/{drive}/items/{root_id}"
    root = request_metadata(intake, base, {"$select": "id,name,folder,remoteItem"}, "ROOT")
    if (root.get("id") != root_id or root.get("name") != "SalCAPA Intake"
            or not isinstance(root.get("folder"), dict) or "remoteItem" in root):
        raise CensusFailure("ROOT_BOUNDARY_MISMATCH")
    endpoint = base + "/delta"
    page, params, visited, items = endpoint, {"$select":
        "id,name,size,file,folder,remoteItem,deleted,eTag,cTag,lastModifiedDateTime,parentReference,createdBy,lastModifiedBy,webUrl",
        "$top": "200"}, set(), {}
    while page:
        if page in visited or len(visited) >= 2000:
            raise CensusFailure("PAGINATION_BOUND_EXCEEDED")
        visited.add(page)
        payload = request_metadata(intake, page, params, "PAGE")
        values = payload.get("value")
        next_link, delta_link = payload.get("@odata.nextLink"), payload.get("@odata.deltaLink")
        if not isinstance(values, list) or len(values) > 1000 or bool(next_link) == bool(delta_link):
            raise CensusFailure("PAGE_SHAPE_INVALID")
        link = next_link or delta_link
        parsed, expected = urlparse(str(link)), urlparse(endpoint)
        if (not isinstance(link, str) or len(link) > 8192 or parsed.scheme != "https"
                or parsed.netloc != "graph.microsoft.com" or parsed.path != expected.path
                or not parsed.query or parsed.fragment):
            raise CensusFailure("CONTINUATION_SCOPE_INVALID")
        for item in values:
            if not isinstance(item, dict) or not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", str(item.get("id", ""))):
                raise CensusFailure("ITEM_ID_INVALID")
            key = item["id"]
            if "deleted" in item:
                items.pop(key, None)
                continue
            if "remoteItem" in item:
                raise CensusFailure("SHORTCUT_REJECTED")
            if key == root_id:
                if not isinstance(item.get("folder"), dict):
                    raise CensusFailure("ROOT_TYPE_CHANGED")
                continue
            parent = item.get("parentReference") or {}
            if not isinstance(parent,dict):
                raise CensusFailure("PARENT_ID_INVALID")
            if parent.get("driveId") not in (None, "", drive):
                raise CensusFailure("DRIVE_MISMATCH")
            if not re.fullmatch(r"[A-Za-z0-9_!.-]{8,256}", str(parent.get("id", ""))):
                raise CensusFailure("PARENT_ID_INVALID")
            name = item.get("name")
            if (not isinstance(name, str) or not name or name in (".", "..")
                    or "/" in name or "\\" in name or len(name) > 512):
                raise CensusFailure("NAME_INVALID")
            file, folder = isinstance(item.get("file"), dict), isinstance(item.get("folder"), dict)
            if file == folder:
                raise CensusFailure("ITEM_TYPE_INVALID")
            if file:
                if (not isinstance(item.get("size"), int) or isinstance(item["size"], bool)
                        or item["size"] < 0 or not item.get("eTag") or not item.get("lastModifiedDateTime")):
                    raise CensusFailure("SOURCE_PROVENANCE_INCOMPLETE")
            items[key] = item
            if len(items) > 100000:
                raise CensusFailure("ITEM_BOUND_EXCEEDED")
        page, params = next_link, None
    top_items = [(key,item) for key,item in items.items() if item["parentReference"]["id"] == root_id]
    tops = {item["name"]: key for key,item in top_items}
    if set(tops) != set(AREA_CODES) or len(top_items) != 7:
        raise CensusFailure("TOP_LEVEL_BOUNDARY_CHANGED")
    if any(not isinstance(items[key].get("folder"), dict) for key in tops.values()):
        raise CensusFailure("TOP_LEVEL_TYPE_CHANGED")
    files = {}
    for key, item in items.items():
        if not isinstance(item.get("file"), dict):
            continue
        path, seen, current = [item["name"]], {key}, item["parentReference"]["id"]
        while current != root_id:
            if current in seen or current not in items or len(seen) > 1000:
                raise CensusFailure("ANCESTRY_INVALID")
            seen.add(current)
            folder = items[current]
            if not isinstance(folder.get("folder"), dict):
                raise CensusFailure("ANCESTOR_NOT_FOLDER")
            path.append(folder["name"])
            if folder["parentReference"]["id"] == root_id:
                area, area_id = folder["name"], current
            current = folder["parentReference"]["id"]
        if len(path) < 2 or path[-1] not in AREA_CODES:
            raise CensusFailure("SOURCE_AREA_INVALID")
        try:
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
        except Exception:
            raise CensusFailure("METADATA_HELPER_REJECTED") from None
        files[key] = {"item_id": key, "area_id": area_id, "area": area,
            "parent_id": item["parentReference"]["id"], "name": item["name"],
            "etag": str(item["eTag"]), "size": item["size"], "metadata_json": canonical(metadata)}
    return files

def snapshot_digest(inventory):
    return hashlib.sha256(canonical(inventory).encode()).hexdigest()

def inventory_diff(before, after):
    """Counts overlap across change types; no source value or identifier is emitted."""
    common = set(before) & set(after)
    result = {"added":len(set(after)-set(before)),"removed":len(set(before)-set(after)),
        "changed":0,"etag":0,"size":0,"parent_or_area":0,"name":0,"relative_path":0,
        "modified_time":0,"content_tag":0,"mime":0,"attribution":0,"trusted_url":0,
        "other_metadata":0,"other_row_fields":0,"serialization_only":0}
    expected_row = {"item_id","area_id","area","parent_id","name","etag","size","metadata_json"}
    try:
        for key in common:
            left,right = before[key],after[key]
            if not isinstance(left,dict) or not isinstance(right,dict):
                raise ValueError
            if left == right:
                continue
            result["changed"] += 1
            a,b = json.loads(left["metadata_json"]),json.loads(right["metadata_json"])
            if not isinstance(a,dict) or not isinstance(b,dict):
                raise ValueError
            def changed(values,x,y):
                return any((name in x) != (name in y) or x.get(name) != y.get(name) for name in values)
            for label,fields in (("etag",("etag",)),("size",("size",)),
                ("parent_or_area",("parent_id","area_id","area")),("name",("name",))):
                result[label] += int(changed(fields,left,right))
            for label,fields in (("relative_path",("relative_path",)),("modified_time",("last_modified",)),
                ("content_tag",("ctag",)),("mime",("mime_type",)),
                ("attribution",("source_owner","source_owner_id","last_modified_by")),
                ("trusted_url",("web_url",))):
                result[label] += int(changed(fields,a,b))
            other_meta = (set(a)|set(b))-{"relative_path","last_modified","ctag","mime_type",
                                                   "source_owner","source_owner_id","last_modified_by","web_url"}
            result["other_metadata"] += int(changed(other_meta,a,b))
            extra_row = (set(left)|set(right))-expected_row
            result["other_row_fields"] += int(changed(extra_row|{"item_id"},left,right))
            result["serialization_only"] += int(a == b and left["metadata_json"] != right["metadata_json"])
    except (KeyError,TypeError,ValueError):
        raise CensusFailure("DIFF_INPUT_INVALID") from None
    return result

def acquire_inventory(intake, *, inventory_fn=scoped_inventory):
    global INVENTORY_ATTEMPTS,INVENTORIES_COMPLETED
    INVENTORY_ATTEMPTS += 1
    number = INVENTORY_ATTEMPTS
    value = inventory_fn(intake)
    INVENTORIES_COMPLETED += 1
    print(f"STABILITY_SAMPLE_{number}_COMPLETE=1",flush=True)
    print(f"STABILITY_SAMPLE_{number}_FILES={len(value)}",flush=True)
    print(f"STABILITY_SAMPLE_{number}_SHA256={snapshot_digest(value)}",flush=True)
    print(f"STABILITY_SAMPLE_{number}_AT={datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",flush=True)
    return value

def emit_diff(before, after, label):
    counts = inventory_diff(before,after)
    for key,count in counts.items():
        print(f"STABILITY_{label}_{key.upper()}={count}",flush=True)
    return counts

def establish_stable_inventory(intake, *, inventory_fn=scoped_inventory, max_observations=MAX_OBSERVATIONS):
    if not 2 <= max_observations <= MAX_OBSERVATIONS:
        raise ValueError("Observation bound invalid")
    previous = acquire_inventory(intake,inventory_fn=inventory_fn)
    for number in range(2,max_observations+1):
        current = acquire_inventory(intake,inventory_fn=inventory_fn)
        emit_diff(previous,current,f"PAIR_{number-1}_{number}")
        if previous == current:
            print("STABILITY_CONSECUTIVE_COMPLETE_INVENTORIES_EQUAL=1",flush=True)
            return current
        previous = current
    raise CensusFailure("STABILITY_NOT_ESTABLISHED")

def prior_state_readback(conn):
    previous = (
        ("PRIOR_CENSUS","salus-unresolved-recovery-census-20261115"),
        ("PRIOR_GAP_RECONCILIATION","salus-representation-gap-reconciliation-20261115"),
        ("THIS_TASK",TASK_KEY),
    )
    for label,key in previous:
        count = int(conn.execute("SELECT COUNT(*) FROM m365_knowledge_consideration_receipts WHERE actor LIKE ?",
                  ("System Administrator - task consideration " + key + " / %",)).fetchone()[0])
        print(f"STABILITY_{label}_DURABLE_RECEIPTS={count}",flush=True)
        if count:
            raise CensusFailure("PRIOR_TASK_RECEIPTS_PRESENT")
    if getattr(conn,"backend","sqlite") == "postgres":
        exists = bool(conn.execute("SELECT to_regclass('m365_knowledge_representation_batches')").fetchone()[0])
    else:
        exists = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='m365_knowledge_representation_batches'").fetchone())
    count = 0 if not exists else int(conn.execute(
        "SELECT COUNT(*) FROM m365_knowledge_representation_batches WHERE operation_key=?",
        ("salus-representation-gap-reconciliation-20261115",)).fetchone()[0])
    print(f"STABILITY_PRIOR_ENROLLMENT_BATCHES={count}",flush=True)
    if count:
        raise CensusFailure("PRIOR_ENROLLMENT_BATCH_PRESENT")

def verify_membership(conn, inventory):
    missing = set(inventory)-represented_ids(conn)
    print(f"STABILITY_CURRENT_SOURCE_FILES={len(inventory)}",flush=True)
    print(f"STABILITY_MISSING_CURRENT_SOURCE_FILES={len(missing)}",flush=True)
    for area,code in AREA_CODES.items():
        print(f"STABILITY_MISSING_AREA_{code}={sum(inventory[key]['area'] == area for key in missing)}",flush=True)
    if missing:
        raise CensusFailure("MISSING_REPRESENTATION")

def verified_search(conn, intake, inventory, *, inventory_fn=scoped_inventory,
                    minimum_boundary=22447, minimum_represented=22457):
    def stable_source():
        value = acquire_inventory(intake,inventory_fn=inventory_fn)
        emit_diff(inventory,value,"SEARCH_CHECK")
        if value != inventory:
            raise CensusFailure("SOURCE_CHANGED_DURING_SEARCH")
        return {key:item["etag"] for key,item in inventory.items()}
    return run_search(conn,source_census_fn=stable_source,
                      minimum_boundary=minimum_boundary,minimum_represented=minimum_represented)

def fresh_receipt_readback(conn, summaries):
    if len(summaries) != len(QUERIES) or len({s["receipt_id"] for s in summaries}) != len(QUERIES):
        raise CensusFailure("RECOVERY_RECEIPT_DISAGREEMENT")
    for summary,(label,query) in zip(summaries,QUERIES):
        row=conn.execute("SELECT * FROM m365_knowledge_consideration_receipts WHERE receipt_id=?",
                         (summary["receipt_id"],)).fetchone()
        expected={"query_sha256":hashlib.sha256(query.strip().encode()).hexdigest(),
            "boundary_count":summary["boundary_files"],"considered_count":summary["considered_files"],
            "matched_count":summary["matched_files"],"content_available_count":summary["content_available_files"],
            "metadata_only_count":summary["metadata_only_or_unresolved_files"],
            "governed_hold_count":summary["governed_hold_files"],
            "actor":ACTOR+" / "+label,"created_at":summary["receipt_created_at"]}
        if row is None or summary["receipt_actor"] != expected["actor"] or any(row[k] != v for k,v in expected.items()):
            raise CensusFailure("RECOVERY_RECEIPT_DISAGREEMENT")
    count=int(conn.execute("SELECT COUNT(*) FROM m365_knowledge_consideration_receipts WHERE actor LIKE ?",
                           (ACTOR+" / %",)).fetchone()[0])
    if count != len(QUERIES):
        raise CensusFailure("RECOVERY_RECEIPT_DISAGREEMENT")
    print(f"STABILITY_FRESH_CONNECTION_RECEIPTS_VERIFIED={count}",flush=True)

def emit_failure(exc):
    code=exc.code if isinstance(exc,CensusFailure) and isinstance(exc.code,str) and exc.code in FAILURE_CODES else "UNEXPECTED_FAILURE"
    print(f"STABILITY_FAILURE_CODE={code}",flush=True)
    print(f"STABILITY_FAILURE_STAGE={STAGE}",flush=True)
    print(f"STABILITY_INVENTORY_ATTEMPTS={INVENTORY_ATTEMPTS}",flush=True)
    print(f"STABILITY_INVENTORIES_COMPLETED={INVENTORIES_COMPLETED}",flush=True)
    print(f"STABILITY_NEW_TASK_RECEIPTS_CREATED={CREATED_RECEIPTS}",flush=True)


def main():
    global STAGE,INVENTORY_ATTEMPTS,INVENTORIES_COMPLETED,CREATED_RECEIPTS
    INVENTORY_ATTEMPTS=INVENTORIES_COMPLETED=CREATED_RECEIPTS=0
    if os.getenv("SALUS_DB_BACKEND","").lower() != "postgres":
        raise RuntimeError("Managed PostgreSQL required")
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config,GovernedM365Intake
    conn,intake = None,None
    try:
        STAGE="durable_prior_state"
        conn=connect_database()
        prior_state_readback(conn)
        conn.close()
        conn=None
        intake=GovernedM365Intake(GovernedM365Config.from_environment())
        STAGE="stable_inventory_observations"
        inventory=establish_stable_inventory(intake)
        if len(inventory)<22447:
            raise CensusFailure("BOUNDARY_BELOW_MINIMUM")
        STAGE="current_representation_readback"
        conn=connect_database()
        verify_membership(conn,inventory)
        before=unresolved_snapshot(conn)
        STAGE="stable_census_and_receipts"
        summaries=verified_search(conn,intake,inventory)
        STAGE="recovery_metadata_readback"
        after=unresolved_snapshot(conn)
        if before != after:
            raise CensusFailure("RECOVERY_METADATA_CHANGED")
        if any(s["metadata_only_or_unresolved_files"] != after["metadata_only_or_unresolved_files"]
               or s["content_available_files"] != after["service_content_available_files"] for s in summaries):
            raise CensusFailure("RECOVERY_RECEIPT_DISAGREEMENT")
        conn.close()
        conn=connect_database()
        STAGE="fresh_receipt_readback"
        fresh_receipt_readback(conn,summaries)
        for key,value in after.items():
            if isinstance(value,dict):
                for label,count in sorted(value.items()):
                    print(f"RECOVERY_{key.upper()}_{label.upper()}={count}",flush=True)
            else:
                print(f"RECOVERY_{key.upper()}={value}",flush=True)
        print("STABILITY_INVENTORIES_COMPLETED="+str(INVENTORIES_COMPLETED),flush=True)
        print("STABILITY_SOURCE_RECORD_OR_SCHEMA_WRITES=0",flush=True)
        print("STABILITY_SOURCE_CONTENT_DOWNLOADS=0",flush=True)
        print("STABILITY_AUTOMATIC_PROCESSING_ACTIVATED=0",flush=True)
        print("STABILITY_PROTECTED_MEMBER_ACCESS=0",flush=True)
        print("STABILITY_ASSIGNMENT_OR_RELEASE_AUTHORITY=0",flush=True)
        print("STABILITY_CENSUS_COMPLETE=1",flush=True)
        print("RECOVERY_ALL_CONTENT_RESOLVED=0",flush=True)
    except Exception as exc:
        emit_failure(exc)
        raise SystemExit(1) from None
    finally:
        if conn is not None:
            conn.close()
        if intake is not None:
            intake.client.close()
            intake.credential.close()

if __name__ == "__main__":
    main()
