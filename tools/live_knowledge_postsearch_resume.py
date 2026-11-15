"""Receipt-preserving continuation of the consumed recovery-planning task."""
from __future__ import annotations
import hashlib
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

TASK_KEY = "salus-availability-recovery-plan-20261115"
PHASE_KEY = "salus-post-search-recovery-plan-20261115"
STAGE = "not_started"
LAST_PHASE_TIME = None
def represented_ids(conn):
    return {str(row["source_item_id"]) for row in conn.execute("""
        SELECT source_item_id FROM m365_knowledge_candidates
        UNION SELECT source_item_id FROM m365_knowledge_holds WHERE status='Governed Hold'
        UNION SELECT item_id FROM m365_bulk_items WHERE kind='file' AND status<>'Removed'
    """).fetchall()}

KNOWN_CODES = frozenset(["DOCUMENT_ACTIVE_CONTENT","DOCUMENT_ACTIVE_OR_LEGACY_FORMAT","DOCUMENT_PACKAGE_INVALID","DOCUMENT_XML_INVALID","FORMAT_NOT_SUPPORTED","IMAGE_FORMAT_MISMATCH","IMAGE_HEADER_INVALID","MEDIA_FORMAT_MISMATCH","MEDIA_HEADER_INVALID","MEDIA_STREAM_INVALID","MEDIA_STREAM_LIMIT","PDF_ACTIVE_CONTENT","PDF_ENCRYPTED","PDF_HEADER_INVALID","PDF_PAGE_LIMIT","PDF_PARSE_FAILED","TEXT_ENCODING_UNSUPPORTED","DOCUMENT_EXPANSION_LIMIT","IMAGE_METADATA_LIMIT","IMAGE_RESOURCE_LIMIT","MEDIA_RESOURCE_LIMIT","OCR_RESOURCE_LIMIT","PDF_PAGE_CONTENT_LIMIT","PDF_RESOURCE_LIMIT","PDF_SOURCE_LIMIT","TRANSCRIPT_OUTPUT_INVALID","TRANSCRIPTION_CAPACITY_UNAVAILABLE","TRANSCRIPTION_FAILED"])

CATEGORIES = ("governed_hold", "governed_review", "retry_paused", "automatic_retry",
              "complete_without_text", "no_candidate", "other_or_conflicting")

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

FAILURE_CODES = FAILURE_CODES | frozenset(["PLAN_01","PLAN_02","PLAN_03","PLAN_04","PLAN_05","PLAN_06","PLAN_07","PLAN_08","PLAN_09","PLAN_10","PLAN_11","PLAN_12","PLAN_13","PLAN_14","PLAN_15","PLAN_16","PLAN_17","PLAN_18","PLAN_19","PLAN_20"])

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

def verify_membership(conn, inventory):
    missing = set(inventory)-represented_ids(conn)
    print(f"STABILITY_CURRENT_SOURCE_FILES={len(inventory)}",flush=True)
    print(f"STABILITY_MISSING_CURRENT_SOURCE_FILES={len(missing)}",flush=True)
    for area,code in AREA_CODES.items():
        print(f"STABILITY_MISSING_AREA_{code}={sum(inventory[key]['area'] == area for key in missing)}",flush=True)
    if missing:
        raise CensusFailure("MISSING_REPRESENTATION")

PLAN_TABLES = ("m365_knowledge_recovery_plans", "m365_knowledge_recovery_batches",
               "m365_knowledge_recovery_plan_events")

SOURCE_TABLES = ("m365_knowledge_candidates", "m365_knowledge_holds",
                 "m365_bulk_items", "m365_bulk_extraction_checks")

EXPECTED_COHORTS = {"governed_review": 7085, "retry_paused": 733,
                    "automatic_retry": 488, "governed_hold": 93,
                    "other_or_conflicting": 5, "complete_without_text": 0, "no_candidate": 0}

MAX_BATCH = 50

def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()

def scalar(conn, path):
    if getattr(conn, "backend", "sqlite") == "postgres":
        return "COALESCE(p.doc #>> '{" + path + "}','')"
    return "COALESCE(json_extract(c.classification_json,'$." + path.replace(",", ".") + "'),'')"

def json_type(conn, path):
    if getattr(conn, "backend", "sqlite") == "postgres":
        return "COALESCE(jsonb_typeof(p.doc #> '{" + path + "}'),'')"
    return "COALESCE(json_type(c.classification_json,'$." + path.replace(",", ".") + "'),'')"

def read_evidence(conn):
    """SQL projects booleans and metadata; never selects extracted text or raw errors."""
    postgres = getattr(conn, "backend", "sqlite") == "postgres"
    if int(conn.execute("SELECT COUNT(*) FROM m365_knowledge_candidates").fetchone()[0]) > 150000:
        raise CensusFailure("PLAN_01")
    hash_expr = ("p.classification_sha256" if postgres
                 else "sha256text(c.classification_json)")
    text_expr = scalar(conn, "extraction,text")
    # Both engines trim exactly the same explicit whitespace set. The old census
    # boolean is retained separately so its historical meaning is not rewritten.
    whitespace = "char(32)||char(9)||char(10)||char(13)||char(11)||char(12)"
    if postgres:
        whitespace = whitespace.replace("char(", "chr(")
    trim_expr = ("btrim(" if postgres else "trim(") + text_expr + "," + whitespace + ")"
    string_type = "string" if postgres else "text"
    fields = {"extraction_status": "extraction,status", "failure_code": "extraction,failure_code",
              "retry_eligible": "extraction,retry_eligible", "automatic_retry_paused": "extraction,automatic_retry_paused",
              "disposition": "extraction,disposition", "disposition_reason": "extraction,disposition_reason"}
    prefix = ("WITH decoded AS MATERIALIZED (SELECT id, classification_json::jsonb doc,"
        "encode(sha256(convert_to(classification_json,'UTF8')),'hex') classification_sha256,"
        "CASE WHEN classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END legacy_complete "
        "FROM m365_knowledge_candidates) " if postgres else "")
    legacy = ("p.legacy_complete " if postgres else
        "CASE WHEN c.classification_json LIKE '%\"status\": \"Complete\"%' THEN 1 ELSE 0 END legacy_complete ")
    join = " JOIN decoded p ON p.id=c.id" if postgres else ""
    query = (prefix + "SELECT c.id,c.source_drive_id,c.source_item_id,c.source_etag,c.source_sha256,"
             "c.source_size,c.source_modified_at,c.source_archive_item_id,c.source_archive_etag,"
             "c.source_archived_at,c.status,c.decision,c.reviewed_at,c.reviewed_by,c.review_rationale,c.destination_item_id,"
             "c.destination_etag,c.source_removed_at," + hash_expr + " classification_sha256,"
             + ",".join(scalar(conn, path) + " " + name for name, path in fields.items())
             + ",CASE WHEN LENGTH(TRIM(" + text_expr + "))>0 THEN 1 ELSE 0 END has_text,"
             + "CASE WHEN " + json_type(conn, "extraction,text") + "='" + string_type + "' AND LENGTH("
             + trim_expr + ")>0 THEN 1 ELSE 0 END strict_text,"
             + legacy + "FROM m365_knowledge_candidates c" + join + " ORDER BY c.id")
    candidates = [dict(r) for r in conn.execute(query).fetchall()]
    holds = [dict(r) for r in conn.execute(
        "SELECT source_drive_id,source_item_id,source_parent_id,source_etag,source_size,source_modified_at,"
        "source_area,status,hold_reason,research_disposition,teaching_disposition,citation_disposition,"
        "reviewed_by,reviewed_at,review_rationale FROM m365_knowledge_holds WHERE status='Governed Hold' "
        "ORDER BY source_drive_id,source_item_id").fetchall()]
    bulk = [dict(r) for r in conn.execute(
        "SELECT drive_id,pending_id,item_id,parent_id,etag,size,status,reason,attempts,next_attempt,updated_at,"
        "lease_owner,lease_until FROM m365_bulk_items WHERE kind='file' AND status<>'Removed' "
        "ORDER BY drive_id,pending_id,item_id").fetchall()]
    checks = [dict(r) for r in conn.execute(
        "SELECT candidate_id,attempts,next_attempt,lease_owner,lease_until,checked_at,last_code "
        "FROM m365_bulk_extraction_checks ORDER BY candidate_id").fetchall()]
    represented = sorted(represented_ids(conn))
    if len(represented) > 100000 or any(len(v) > 150000 for v in (candidates, holds, bulk, checks)):
        raise CensusFailure("PLAN_01")
    return {"represented": represented, "candidates": candidates, "holds": holds,
            "bulk": bulk, "checks": checks}

def cohort(candidates, held):
    statuses = {r["extraction_status"] for r in candidates}
    if held:
        return "governed_hold"
    if len(statuses) > 1:
        return "other_or_conflicting"
    return {"Review Required": "governed_review", "Retry Paused": "retry_paused",
            "Automatic Retry Required": "automatic_retry", "Complete": "complete_without_text"}.get(
                next(iter(statuses), ""), "other_or_conflicting" if candidates else "no_candidate")

def make_plan(evidence, inventory, *, clock, expected_cohorts=EXPECTED_COHORTS, expected_discrepancies=5):
    """One source appears once in recovery, with every candidate version attached."""
    represented = set(evidence["represented"])
    by_source, bulk_by_source, hold_by_source = {}, {}, {}
    checks = {r["candidate_id"]: r for r in evidence["checks"]}
    for r in evidence["candidates"]:
        if r["source_item_id"] not in represented:
            raise CensusFailure("PLAN_02")
        by_source.setdefault(r["source_item_id"], []).append(r)
    for r in evidence["bulk"]:
        bulk_by_source.setdefault(r["item_id"], []).append(r)
    for r in evidence["holds"]:
        hold_by_source.setdefault(r["source_item_id"], []).append(r)
    available = {s for s, rows in by_source.items() if any(r["legacy_complete"] for r in rows)}
    exact = {s for s, rows in by_source.items()
             if any(r["extraction_status"] == "Complete" and r["has_text"] for r in rows)}
    strict = {s for s, rows in by_source.items()
              if any(r["extraction_status"] == "Complete" and r["strict_text"] for r in rows)}
    unresolved = represented - available
    discrepancies = available - exact
    if exact != strict or exact - available or len(discrepancies) != expected_discrepancies:
        raise CensusFailure("PLAN_03")

    def record(source):
        current = inventory.get(source)
        versions = []
        for raw in by_source.get(source, []):
            r = dict(raw)
            check = checks.get(r["id"])
            r["checkpoint"] = check
            r["checkpoint_state"] = ("missing" if check is None else
                "leased" if int(check["lease_until"]) >= clock and check["lease_owner"] else
                "future" if int(check["next_attempt"]) > clock else "due")
            r["source_version_matches_current"] = bool(current and r["source_etag"] == current["etag"])
            r["archive_metadata_recorded"] = bool(r["source_archive_item_id"])
            r["archive_bytes_verified_by_this_task"] = False
            r["failure_code_known"] = not r["failure_code"] or r["failure_code"] in KNOWN_CODES
            versions.append(r)
        return {"source_item_id": source, "current_source": None if current is None else
                {k: current[k] for k in ("etag", "size", "parent_id", "area_id", "area")},
                "current_metadata_sha256": digest(current) if current else None,
                "holds": hold_by_source.get(source, []), "bulk_checkpoints": bulk_by_source.get(source, []),
                "candidate_versions": versions, "processing_authorized": False,
                "human_qualification": "Unvetted Candidate"}

    availability = []
    for source in sorted(discrepancies):
        item = record(source)
        for r in item["candidate_versions"]:
            r["availability_condition"] = (
                "EXACT_COMPLETE_EMPTY_TEXT" if r["legacy_complete"] and r["extraction_status"] == "Complete" else
                "BROAD_COMPLETE_MATCH_OUTSIDE_EXTRACTION_STATUS" if r["legacy_complete"] else
                "NOT_COUNTED_BY_LEGACY_PREDICATE")
        item["disposition"] = "Availability exception; do not count as verified extracted text"
        item["next_action"] = "Review exact candidate/version evidence; govern prospective service correction separately"
        availability.append(item)
    groups, categories, matrix = {}, {k: 0 for k in CATEGORIES}, {}
    overlap = {"multiple_candidate_sources": 0, "no_recorded_archive_sources": 0,
               "active_lease_sources": 0, "historical_only_sources": 0,
               "no_current_version_candidate_sources": 0, "missing_checkpoint_sources": 0}
    for source in sorted(unresolved):
        item = record(source)
        rows = item["candidate_versions"]
        category = cohort(rows, bool(item["holds"]))
        categories[category] += 1
        item["category"] = category
        codes = sorted({r["failure_code"] if r["failure_code"] in KNOWN_CODES else
                        "UNKNOWN" if r["failure_code"] else "EMPTY" for r in rows}) or ["NO_CANDIDATE"]
        item["failure_codes"] = codes
        # Cross-matrix is candidate-correlated, not a multiplication of totals.
        for r in rows:
            code = r["failure_code"] if r["failure_code"] in KNOWN_CODES else "UNKNOWN" if r["failure_code"] else "EMPTY"
            key = category + "/" + code + "/" + r["checkpoint_state"]
            matrix[key] = matrix.get(key, 0) + 1
        archived = any(r["archive_metadata_recorded"] for r in rows)
        leased = any(r["checkpoint_state"] == "leased" for r in rows) or any(
            r["lease_owner"] and int(r["lease_until"]) >= clock for r in item["bulk_checkpoints"])
        current_version = any(r["source_version_matches_current"] for r in rows)
        traits = {"multiple_candidate_sources": len(rows) > 1,
                  "no_recorded_archive_sources": bool(rows) and not archived,
                  "active_lease_sources": leased, "historical_only_sources": source not in inventory,
                  "no_current_version_candidate_sources": source in inventory and not current_version,
                  "missing_checkpoint_sources": any(r["checkpoint"] is None for r in rows)}
        for k, flag in traits.items():
            overlap[k] += int(flag)
        item["traits"] = traits
        item["required_gate"] = {
            "governed_hold": "Source owner: resolve hold authority; preserve hold until separately approved",
            "governed_review": "Qualified source review: retain original; approve safe derivative/remedy with provenance",
            "retry_paused": "Processor owner: validated processor release and exact-head approval before resumption",
            "automatic_retry": "Processor owner: bounded same-candidate due/lease/archive/hash preflight and separate batch approval",
        }.get(category, "Governance owner: characterize conflicting versions or missing evidence before recovery")
        # Split by exact failure-code signature, archive/current-version, and lease
        # traits. Mixed-version records remain together, never silently deduplicated.
        group = canonical([category, codes, archived, current_version, leased, len(rows) > 1])
        groups.setdefault(group, []).append(item)
    if categories != expected_cohorts or sum(categories.values()) != len(unresolved):
        raise CensusFailure("PLAN_04")
    batches = []
    for group in sorted(groups):
        for start in range(0, len(groups[group]), MAX_BATCH):
            records = groups[group][start:start + MAX_BATCH]
            batches.append({"batch_key": "batch-" + str(len(batches) + 1).zfill(4),
                "state": "Prepared - Not Authorized for Processing", "category": records[0]["category"],
                "failure_codes": records[0]["failure_codes"], "records": records,
                "record_count": len(records), "processing_authorized": False})
    enumerated = [r["source_item_id"] for b in batches for r in b["records"]]
    if len(enumerated) != len(set(enumerated)) or set(enumerated) != unresolved or discrepancies & set(enumerated):
        raise CensusFailure("PLAN_05")
    summary = {"represented_files": len(represented), "legacy_content_available": len(available),
        "exact_complete_nonempty_text": len(exact), "strict_complete_text": len(strict),
        "availability_exceptions": len(availability), "unresolved_files": len(unresolved),
        "categories": categories, "overlapping_traits": overlap, "candidate_cross_matrix": matrix,
        "batch_count": len(batches), "prepared_sources": len(enumerated), "processing_authorized": False}
    conditions = {}
    for item in availability:
        for r in item["candidate_versions"]:
            k = r["availability_condition"]
            conditions[k] = conditions.get(k, 0) + 1
    summary["availability_candidate_conditions"] = conditions
    return {"operation_key": TASK_KEY, "state": "Prepared - Not Authorized for Processing",
        "created_at": datetime.fromtimestamp(clock, timezone.utc).replace(microsecond=0).isoformat(),
        "inventory_sha256": snapshot_digest(inventory), "evidence_sha256": digest(evidence),
        "summary": summary, "availability_exceptions": availability, "batches": batches}

def create_plan_tables(conn):
    # execute() rather than SQLite executescript(): DDL belongs to this transaction.
    for sql in (
        "CREATE TABLE IF NOT EXISTS m365_knowledge_recovery_plans (operation_key TEXT PRIMARY KEY, "
        "state TEXT NOT NULL, manifest_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL)",
        "CREATE TABLE IF NOT EXISTS m365_knowledge_recovery_batches (operation_key TEXT NOT NULL, batch_key TEXT NOT NULL, "
        "record_count INTEGER NOT NULL, payload_sha256 TEXT NOT NULL, payload_json TEXT NOT NULL, PRIMARY KEY(operation_key,batch_key))",
        "CREATE TABLE IF NOT EXISTS m365_knowledge_recovery_plan_events (operation_key TEXT PRIMARY KEY, "
        "event_type TEXT NOT NULL, detail_json TEXT NOT NULL, created_at TEXT NOT NULL)"):
        conn.execute(sql)

def verify_plan(conn, plan):
    row = conn.execute("SELECT * FROM m365_knowledge_recovery_plans WHERE operation_key=?", (TASK_KEY,)).fetchone()
    expected = {k: v for k, v in plan.items() if k != "batches"}
    expected["batch_hashes"] = [{"batch_key": b["batch_key"], "sha256": digest(b)} for b in plan["batches"]]
    if (row is None or row["payload_json"] != canonical(expected) or row["manifest_sha256"] != digest(expected)
            or row["state"] != plan["state"] or row["created_at"] != plan["created_at"]):
        raise CensusFailure("PLAN_11")
    rows = conn.execute("SELECT * FROM m365_knowledge_recovery_batches WHERE operation_key=? ORDER BY batch_key", (TASK_KEY,)).fetchall()
    if len(rows) != len(plan["batches"]):
        raise CensusFailure("PLAN_12")
    for row, batch in zip(rows, plan["batches"]):
        if (row["batch_key"] != batch["batch_key"] or row["record_count"] != batch["record_count"]
                or row["payload_json"] != canonical(batch) or row["payload_sha256"] != digest(batch)):
            raise CensusFailure("PLAN_13")
    event = conn.execute("SELECT * FROM m365_knowledge_recovery_plan_events WHERE operation_key=?", (TASK_KEY,)).fetchone()
    expected_event = {"manifest_sha256": digest(expected), "summary": plan["summary"], "processing_authorized": False}
    if (event is None or event["event_type"] != "AvailabilityReconciledAndRecoveryBatchesPrepared"
            or event["created_at"] != plan["created_at"] or event["detail_json"] != canonical(expected_event)):
        raise CensusFailure("PLAN_14")
    return digest(expected)



EXPECTED_RECEIPTS = [
    {
        "receipt_id": "95838b67-b96f-4d75-a079-d1c4b72bfddb",
        "query_sha256": "ccf6bfc899b61cc79efd9d538bd6151e4a8efb71baff9d8b11cab196e13badcd",
        "boundary_count": 23622,
        "considered_count": 23632,
        "matched_count": 23540,
        "content_available_count": 15228,
        "metadata_only_count": 8404,
        "governed_hold_count": 93,
        "actor": "System Administrator - task consideration salus-availability-recovery-plan-20261115 / availability_reconciliation",
        "created_at": "2026-11-15T17:59:42+00:00"
    },
    {
        "receipt_id": "fb31513b-df74-4e08-8a33-40f63ea306f6",
        "query_sha256": "b15a3882401cf9d872fca236a22276c70f7af8371010a248a5afb917634917aa",
        "boundary_count": 23622,
        "considered_count": 23632,
        "matched_count": 23539,
        "content_available_count": 15228,
        "metadata_only_count": 8404,
        "governed_hold_count": 93,
        "actor": "System Administrator - task consideration salus-availability-recovery-plan-20261115 / recovery_batches",
        "created_at": "2026-11-15T18:00:04+00:00"
    },
    {
        "receipt_id": "4a7de341-6c03-4233-9b9f-41fdcf43abd8",
        "query_sha256": "4de57adc7ec6d84703b8464b25862a7840c7b1e478bde235f773a85d655b3dc6",
        "boundary_count": 23622,
        "considered_count": 23632,
        "matched_count": 23632,
        "content_available_count": 15228,
        "metadata_only_count": 8404,
        "governed_hold_count": 93,
        "actor": "System Administrator - task consideration salus-availability-recovery-plan-20261115 / safety_and_contrary",
        "created_at": "2026-11-15T18:00:59+00:00"
    },
    {
        "receipt_id": "99bf8254-40d4-4327-8511-f834127623ef",
        "query_sha256": "3c21a55211fe2bcfd3e0f887f4db31e35285fdea900cd483448643f03f0e5e9e",
        "boundary_count": 23622,
        "considered_count": 23632,
        "matched_count": 23539,
        "content_available_count": 15228,
        "metadata_only_count": 8404,
        "governed_hold_count": 93,
        "actor": "System Administrator - task consideration salus-availability-recovery-plan-20261115 / verification",
        "created_at": "2026-11-15T18:01:28+00:00"
    }
]
RECEIPT_TABLE = "m365_knowledge_consideration_receipts"
BASELINE_SHA256 = "7836ad36e47829cdf3bf34ae269d5868017cee39759ae314da6912f0945ac3a9"
TRANSACTION_BUDGET_SECONDS = 60
COMMIT_ATTEMPTED = 0
COMMIT_ACKNOWLEDGED = 0
FAILURE_CODES = FAILURE_CODES | frozenset(["RECEIPT_PRESTATE", "TARGET_NOT_EMPTY", "SOURCE_CORE_DRIFT",
    "COHORT_BASELINE_DRIFT", "TRANSACTION_BUDGET", "QUERY_DENIED", "SOURCE_INVENTORY_CHANGED",
    "INDEPENDENT_READBACK_CHANGED", "PLANNING_BUSY"])


class PlanningConnection:
    """Permit source reads/short locks and append-only writes to three plan tables."""
    def __init__(self, inner):
        self.inner = inner
        self.backend = getattr(inner, "backend", "sqlite")
        self.writes_enabled = False
        self.deadline = None
        self.clock = time.monotonic

    def _execute_checked(self, sql, params):
        if self.deadline is not None:
            remaining = self.deadline - self.clock()
            if remaining <= 0:
                raise CensusFailure("TRANSACTION_BUDGET")
            if self.backend == "postgres":
                milliseconds = max(1, min(30000, int(remaining * 1000)))
                self.inner.execute("SET LOCAL statement_timeout='" + str(milliseconds) + "ms'")
        return self.inner.execute(sql, params)

    def execute(self, sql, params=()):
        # SQL is static reviewed source; private values stay in bound parameters.
        clean = re.sub(r"'(?:''|[^'])*'", "''", sql).strip().rstrip(';').strip()
        if ';' in clean or '--' in clean or '/*' in clean:
            raise CensusFailure("QUERY_DENIED")
        upper = clean.upper()
        if upper.startswith(("SELECT ", "WITH ")) and not re.search(r'\b(INSERT|UPDATE|DELETE|MERGE|DROP|ALTER|TRUNCATE|GRANT|REVOKE|CALL|COPY)\b', upper):
            return self._execute_checked(sql, params)
        if upper.startswith("SET LOCAL LOCK_TIMEOUT=") or upper.startswith("SET LOCAL STATEMENT_TIMEOUT="):
            return self._execute_checked(sql, params)
        if upper == "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY":
            return self._execute_checked(sql, params)
        if self.backend == "sqlite" and upper == "BEGIN IMMEDIATE":
            return self._execute_checked(sql, params)
        if upper.startswith("LOCK TABLE "):
            match = re.fullmatch(r'LOCK TABLE ([A-Z0-9_, ]+) IN SHARE MODE NOWAIT', upper)
            if match and set(v.strip().lower() for v in match[1].split(',')) <= set((*SOURCE_TABLES, RECEIPT_TABLE)):
                return self._execute_checked(sql, params)
        if self.writes_enabled:
            match = re.match(r'(?:CREATE TABLE IF NOT EXISTS|INSERT INTO) ([a-z0-9_]+)\b', clean, re.I)
            if match and match[1].lower() in PLAN_TABLES:
                return self._execute_checked(sql, params)
        raise CensusFailure("QUERY_DENIED")

    def commit(self):
        return self.inner.commit()

    def rollback(self):
        return self.inner.rollback()

    def close(self):
        return self.inner.close()


def phase(name):
    global STAGE, LAST_PHASE_TIME
    now = time.monotonic()
    if LAST_PHASE_TIME is not None:
        print("POSTSEARCH_PREVIOUS_PHASE_ELAPSED_MS=" + str(int((now-LAST_PHASE_TIME)*1000)), flush=True)
    STAGE = name
    LAST_PHASE_TIME = now
    print("POSTSEARCH_PHASE=" + name, flush=True)
    print("POSTSEARCH_PHASE_STARTED_AT=" + datetime.now(timezone.utc).replace(microsecond=0).isoformat(), flush=True)


def preserved_receipts(conn, expected=EXPECTED_RECEIPTS):
    rows = [dict(r) for r in conn.execute("SELECT * FROM " + RECEIPT_TABLE + " WHERE actor LIKE ? ORDER BY actor",
        ("System Administrator - task consideration " + TASK_KEY + " / %",)).fetchall()]
    if rows != sorted(expected, key=lambda r: r["actor"]):
        raise CensusFailure("RECEIPT_PRESTATE")
    return digest(rows)


def target_empty(conn):
    counts = []
    for table in PLAN_TABLES:
        if getattr(conn, "backend", "sqlite") == "postgres":
            present = bool(conn.execute("SELECT to_regclass(?)", (table,)).fetchone()[0])
        else:
            present = bool(conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone())
        counts.append(int(conn.execute("SELECT COUNT(*) FROM " + table + " WHERE operation_key=?", (TASK_KEY,)).fetchone()[0]) if present else 0)
    for name, count in zip(("PLANS", "BATCHES", "EVENTS"), counts):
        print("POSTSEARCH_PRESTATE_" + name + "=" + str(count), flush=True)
    if any(counts):
        raise CensusFailure("TARGET_NOT_EMPTY")


def baseline_digest(evidence):
    # Same accepted projection as #1237/#1245, derived without another JSON scan.
    fingerprints = [(r["source_item_id"], r["id"], r["source_sha256"], r["source_archive_item_id"],
        r["extraction_status"], r["failure_code"], r["has_text"], r["legacy_complete"]) for r in evidence["candidates"]]
    return digest({"represented": evidence["represented"], "holds": sorted({r["source_item_id"] for r in evidence["holds"]}),
                   "candidates": fingerprints})


def invariant_view(evidence):
    # Scheduling changes are observed afresh, not mistaken for source approval.
    scheduling = {"attempts", "next_attempt", "updated_at", "lease_owner", "lease_until"}
    return {"represented": evidence["represented"], "candidates": evidence["candidates"], "holds": evidence["holds"],
            "bulk": [{k: v for k, v in row.items() if k not in scheduling} for row in evidence["bulk"]]}


def assert_invariants(before, after):
    if invariant_view(before) != invariant_view(after):
        raise CensusFailure("SOURCE_CORE_DRIFT")


def scheduling_changes(before, after):
    def changed(left, right, key):
        a = {tuple(r[k] for k in key): r for r in left}
        b = {tuple(r[k] for k in key): r for r in right}
        return sum(a.get(k) != b.get(k) for k in a.keys() | b.keys())
    return {"extraction_checkpoints": changed(before["checks"], after["checks"], ("candidate_id",)),
            "bulk_checkpoints": changed(before["bulk"], after["bulk"], ("drive_id", "pending_id", "item_id"))}


def prepare_atomic(conn, preview, inventory, *, expected_receipts=EXPECTED_RECEIPTS,
                   expected_baseline=BASELINE_SHA256, expected_cohorts=EXPECTED_COHORTS,
                   expected_discrepancies=5, fail_after_batches=False, monotonic=time.monotonic):
    global COMMIT_ATTEMPTED, COMMIT_ACKNOWLEDGED
    COMMIT_ATTEMPTED = COMMIT_ACKNOWLEDGED = 0
    started = monotonic()
    conn.deadline = started + TRANSACTION_BUDGET_SECONDS
    conn.clock = monotonic
    def budget():
        if monotonic() - started > TRANSACTION_BUDGET_SECONDS:
            raise CensusFailure("TRANSACTION_BUDGET")
    try:
        phase("commit_lock_precheck")
        if conn.backend == "postgres":
            conn.execute("SET LOCAL lock_timeout='2s'")
            conn.execute("SET LOCAL statement_timeout='30s'")
            if not conn.execute("SELECT pg_try_advisory_xact_lock(674160041245)").fetchone()[0]:
                raise CensusFailure("PLANNING_BUSY")
            conn.execute("LOCK TABLE " + ",".join((*SOURCE_TABLES, RECEIPT_TABLE)) + " IN SHARE MODE NOWAIT")
        else:
            conn.execute("BEGIN IMMEDIATE")
        receipt_sha = preserved_receipts(conn, expected_receipts)
        target_empty(conn)
        phase("locked_current_metadata")
        current = read_evidence(conn)
        assert_invariants(preview, current)
        if baseline_digest(current) != expected_baseline:
            raise CensusFailure("COHORT_BASELINE_DRIFT")
        budget()
        phase("locked_current_plan")
        clock = int(time.time())
        plan = make_plan(current, inventory, clock=clock, expected_cohorts=expected_cohorts,
                         expected_discrepancies=expected_discrepancies)
        plan["continuation"] = {"phase_key": PHASE_KEY, "original_run_id": 43743532577,
            "readback_run_id": 43746748966, "receipt_snapshot_sha256": receipt_sha,
            "preserved_receipt_ids": [r["receipt_id"] for r in expected_receipts],
            "preview_invariant_sha256": digest(invariant_view(preview)),
            "commit_invariant_sha256": digest(invariant_view(current)),
            "observed_scheduling_refresh": scheduling_changes(preview, current),
            "current_metadata_frozen_under_source_locks": True,
            "new_search_receipts_created": 0, "source_record_writes": 0}
        plan["continuation"]["execution_binding"] = {
            "github_run_id": os.getenv("SALUS_POSTSEARCH_RUN_ID", "fixture"),
            "script_sha256": os.getenv("SALUS_POSTSEARCH_SCRIPT_SHA256", "fixture")}
        history = os.getenv("SALUS_POSTSEARCH_HISTORY_B64", "")
        plan["continuation"]["historical_diagnostic"] = decode_history(history) if history else {"query_state": "FIXTURE"}
        budget()
        phase("atomic_planning_rows")
        conn.writes_enabled = True
        create_plan_tables(conn)
        for b in plan["batches"]:
            conn.execute("INSERT INTO m365_knowledge_recovery_batches VALUES(?,?,?,?,?)",
                (TASK_KEY, b["batch_key"], b["record_count"], digest(b), canonical(b)))
            budget()
        if fail_after_batches:
            raise CensusFailure("PLAN_10")
        manifest = {k: v for k, v in plan.items() if k != "batches"}
        manifest["batch_hashes"] = [{"batch_key": b["batch_key"], "sha256": digest(b)} for b in plan["batches"]]
        if len(canonical(plan).encode()) > 24 * 1024 * 1024:
            raise CensusFailure("PLAN_07")
        checksum = digest(manifest)
        conn.execute("INSERT INTO m365_knowledge_recovery_plans VALUES(?,?,?,?,?)",
            (TASK_KEY, plan["state"], checksum, canonical(manifest), plan["created_at"]))
        conn.execute("INSERT INTO m365_knowledge_recovery_plan_events VALUES(?,?,?,?)",
            (TASK_KEY, "AvailabilityReconciledAndRecoveryBatchesPrepared",
             canonical({"manifest_sha256": checksum, "summary": plan["summary"], "processing_authorized": False}), plan["created_at"]))
        phase("precommit_exact_readback")
        verify_plan(conn, plan)
        if preserved_receipts(conn, expected_receipts) != receipt_sha:
            raise CensusFailure("RECEIPT_PRESTATE")
        budget()
        phase("commit")
        COMMIT_ATTEMPTED = 1
        conn.commit()
        COMMIT_ACKNOWLEDGED = 1
        print("POSTSEARCH_COMMIT_WINDOW_MS=" + str(int((monotonic()-started)*1000)), flush=True)
        return plan, current
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.writes_enabled = False
        conn.deadline = None


def independent_readback(conn, plan, committed_evidence, expected_receipts=EXPECTED_RECEIPTS):
    if conn.backend == "postgres":
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL statement_timeout='30s'")
    checksum = verify_plan(conn, plan)
    preserved_receipts(conn, expected_receipts)
    current = read_evidence(conn)
    assert_invariants(committed_evidence, current)
    return checksum, scheduling_changes(committed_evidence, current)


def emit_result(plan, checksum, post_refresh):
    summary = plan["summary"]
    print("POSTSEARCH_TARGET_OPERATION=" + TASK_KEY, flush=True)
    print("POSTSEARCH_PHASE_KEY=" + PHASE_KEY, flush=True)
    history = plan["continuation"]["historical_diagnostic"]
    print("POSTSEARCH_HISTORICAL_QUERY_STATE=" + history["query_state"], flush=True)
    if history["query_state"] != "FIXTURE":
        print("POSTSEARCH_HISTORICAL_FAILURE_CODE=" + history["failure_code"], flush=True)
        print("POSTSEARCH_HISTORICAL_FAILURE_STAGE=" + history["failure_stage"], flush=True)
    for key in ("represented_files", "legacy_content_available", "exact_complete_nonempty_text", "strict_complete_text",
                "availability_exceptions", "unresolved_files", "batch_count", "prepared_sources"):
        print("POSTSEARCH_" + key.upper() + "=" + str(summary[key]), flush=True)
    for category in sorted(EXPECTED_COHORTS):
        print("POSTSEARCH_CATEGORY_" + category.upper() + "=" + str(summary["categories"][category]), flush=True)
    for key in ("multiple_candidate_sources", "no_recorded_archive_sources", "active_lease_sources",
                "historical_only_sources", "no_current_version_candidate_sources", "missing_checkpoint_sources"):
        print("POSTSEARCH_TRAIT_" + key.upper() + "=" + str(summary["overlapping_traits"][key]), flush=True)
    for key in ("EXACT_COMPLETE_EMPTY_TEXT", "BROAD_COMPLETE_MATCH_OUTSIDE_EXTRACTION_STATUS", "NOT_COUNTED_BY_LEGACY_PREDICATE"):
        print("POSTSEARCH_AVAILABILITY_" + key + "=" + str(summary["availability_candidate_conditions"].get(key, 0)), flush=True)
    for label, values in (("PREWRITE", plan["continuation"]["observed_scheduling_refresh"]), ("POSTWRITE", post_refresh)):
        for key, value in values.items():
            print("POSTSEARCH_" + label + "_" + key.upper() + "_CHANGED=" + str(value), flush=True)
    for key, value in (("MANIFEST_SHA256", checksum), ("INVENTORY_SHA256", plan["inventory_sha256"]),
            ("EVIDENCE_SHA256", plan["evidence_sha256"]), ("RECEIPT_SNAPSHOT_SHA256", plan["continuation"]["receipt_snapshot_sha256"]),
            ("CANDIDATE_CROSS_MATRIX_SHA256", digest(summary["candidate_cross_matrix"])), ("CREATED_AT", plan["created_at"])):
        print("POSTSEARCH_" + key + "=" + value, flush=True)
    print("POSTSEARCH_PRESERVED_RECEIPTS=4", flush=True)
    print("POSTSEARCH_NEW_SEARCH_RECEIPTS=0", flush=True)
    print("POSTSEARCH_SOURCE_RECORD_WRITES=0", flush=True)
    print("POSTSEARCH_SOURCE_CONTENT_DOWNLOADS=0", flush=True)
    print("POSTSEARCH_RETRIES_RESUMED=0", flush=True)
    print("POSTSEARCH_FRESH_CONNECTION_VERIFIED=1", flush=True)
    print("POSTSEARCH_PREPARATION_COMPLETE=1", flush=True)


def decode_history(encoded):
    try:
        if len(encoded)>8192:raise ValueError('bound')
        value=json.loads(base64.b64decode(encoded,validate=True).decode())
        states={'UNAVAILABLE','INVALID_RESULT','RECOVERED','NO_FAILURE_MARKER','CONFLICTING_MARKERS','UNRECOGNIZED_CODE'}
        keys={'original_run_id','query_state','failure_code','failure_stage','complete_inventory_markers',
              'query_receipt_markers','accepted_record_count','accepted_records_sha256'}
        if not isinstance(value,dict) or set(value)!=keys or value['original_run_id']!=43743532577:raise ValueError('schema')
        if value['query_state'] not in states:raise ValueError('state')
        if value['failure_code'] not in FAILURE_CODES|{'NOT_OBSERVED'}:raise ValueError('code')
        stages={'NOT_OBSERVED','new_operation_precheck','stable_inventory','source_correlated_recovery_plan',
            'task_search_and_durable_receipts','final_source_stability','atomic_manifest_commit','independent_durable_readback',
            'represented_precheck','duplicate_receipt_precheck','source_census','membership_prequery','create_receipt',
            'verify_durable_receipt','membership_postquery','source_census_readback'}
        if value['failure_stage'] not in stages:raise ValueError('stage')
        if not re.fullmatch(r'[0-9a-f]{64}',value['accepted_records_sha256']):raise ValueError('hash')
        for key,limit in (('complete_inventory_markers',6),('query_receipt_markers',4),('accepted_record_count',300)):
            if not isinstance(value[key],int) or isinstance(value[key],bool) or not 0<=value[key]<=limit:raise ValueError('count')
        return value
    except Exception:
        raise CensusFailure('QUERY_DENIED') from None


def main():
    global INVENTORY_ATTEMPTS, INVENTORIES_COMPLETED
    INVENTORY_ATTEMPTS = INVENTORIES_COMPLETED = 0
    if os.getenv("SALUS_DB_BACKEND", "").lower() != "postgres":
        raise SystemExit("Managed PostgreSQL required")
    from database import connect_database
    from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake
    conn = intake = None
    try:
        phase("preserved_receipt_and_empty_ledger_precheck")
        if (not re.fullmatch(r'[1-9][0-9]{5,19}', os.getenv("SALUS_POSTSEARCH_RUN_ID", "")) or
                not re.fullmatch(r'[0-9a-f]{64}', os.getenv("SALUS_POSTSEARCH_SCRIPT_SHA256", ""))):
            raise CensusFailure("QUERY_DENIED")
        decode_history(os.getenv("SALUS_POSTSEARCH_HISTORY_B64", ""))
        conn = PlanningConnection(connect_database())
        receipt_sha = preserved_receipts(conn)
        print("POSTSEARCH_PRECHECK_RECEIPTS=4", flush=True)
        print("POSTSEARCH_PRECHECK_RECEIPT_SNAPSHOT_SHA256=" + receipt_sha, flush=True)
        target_empty(conn)
        conn.close()
        conn = None
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        phase("stable_inventory")
        inventory = establish_stable_inventory(intake)
        if len(inventory) < 22447:
            raise CensusFailure("BOUNDARY_BELOW_MINIMUM")
        phase("preview_metadata")
        conn = PlanningConnection(connect_database())
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        verify_membership(conn, inventory)
        preserved_receipts(conn)
        preview = read_evidence(conn)
        if baseline_digest(preview) != BASELINE_SHA256:
            raise CensusFailure("COHORT_BASELINE_DRIFT")
        make_plan(preview, inventory, clock=int(time.time()))
        conn.close()
        conn = None
        phase("final_source_inventory")
        final_inventory = acquire_inventory(intake)
        emit_diff(inventory, final_inventory, "POSTSEARCH_FINAL")
        if final_inventory != inventory:
            raise CensusFailure("SOURCE_INVENTORY_CHANGED")
        conn = PlanningConnection(connect_database())
        plan, committed = prepare_atomic(conn, preview, inventory)
        conn.close()
        phase("independent_durable_readback")
        conn = PlanningConnection(connect_database())
        checksum, post_refresh = independent_readback(conn, plan, committed)
        emit_result(plan, checksum, post_refresh)
    except Exception as exc:
        code = exc.code if isinstance(exc, CensusFailure) else "UNEXPECTED_FAILURE"
        sqlstate = getattr(exc, "sqlstate", "")
        if not isinstance(sqlstate, str) or not re.fullmatch(r'[A-Z0-9]{5}', sqlstate):
            sqlstate = "UNAVAILABLE"
        print("POSTSEARCH_FAILURE_CODE=" + code, flush=True)
        print("POSTSEARCH_FAILURE_STAGE=" + STAGE, flush=True)
        print("POSTSEARCH_SQLSTATE=" + sqlstate, flush=True)
        print("POSTSEARCH_COMMIT_ATTEMPTED=" + str(COMMIT_ATTEMPTED), flush=True)
        print("POSTSEARCH_COMMIT_ACKNOWLEDGED=" + str(COMMIT_ACKNOWLEDGED), flush=True)
        print("POSTSEARCH_INVENTORIES_COMPLETED=" + str(INVENTORIES_COMPLETED), flush=True)
        raise SystemExit(1) from None
    finally:
        if conn is not None:
            conn.close()
        if intake is not None:
            intake.client.close()
            intake.credential.close()


if __name__ == "__main__":
    main()
