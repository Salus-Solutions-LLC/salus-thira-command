"""Opt-in metadata diagnostic. No content reads, source writes or app initialization.

Receipts are restricted evidence. Only the fixed aggregate summary goes to stdout.
This tool does not change or replace the runtime's intake/acceptance implementation.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import hmac
import inspect
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import textwrap
import time
from datetime import datetime, timezone

VERSION = "m365-metadata-diagnostic-1"
ROOT = Path(__file__).resolve().parents[1]
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
KEYS = ("id", "name", "etag", "size", "parent_boundary", "listed_snapshot")
PINS = {
    "5dff59b381a0c455f99c6f15d0e2a37c273f4056": (
        "ee43259ebf69912fe7460fef7952852ba9d4263adb290de94e0aa1de83d07d1a",
        "009e4546334e5c135fa5f7c0cf52cd713193dd7156fb2ca1024a183d606d0bfc",
        "sha256:8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c",
        False,
    ),
    "7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3": (
        "6eb7e3232274929e6f45d3fe45ef60bc253696404cb8a1a428f4560f96023c63",
        "a71bf9f3ce0687aeb7c20c73c5ce02a6510ae4048fdd7279872ce16693ec9623",
        "sha256:550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944",
        True,
    ),
}
CODES = {
    "INVALID_CONFIGURATION", "SOURCE_INCOMPATIBLE", "ARCHIVE_BOUND_UNSUPPORTED",
    "LISTING_FAILED", "NO_ITEMS", "METADATA_FAILED", "CONSISTENCY_MISMATCH",
    "TIME_BOUND_REACHED", "RECEIPT_RETENTION_FAILED", "COMPLETE",
    "CLIENT_CLEANUP_FAILED",
}


class DiagnosticFailure(RuntimeError):
    def __init__(self, code, summary=None):
        if code not in CODES or code == "COMPLETE":
            code = "INVALID_CONFIGURATION"
        super().__init__(code)
        self.summary = summary or {"diagnostic_version": VERSION, "status": "failed", "code": code}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def fingerprint(intake):
    source = Path(inspect.getfile(type(intake))).read_bytes().replace(b"\r\n", b"\n")
    method = ast.parse(textwrap.dedent(inspect.getsource(intake.list_files)))
    return hashlib.sha256(source).hexdigest(), hashlib.sha256(
        ast.dump(method, include_attributes=False).encode()
    ).hexdigest()


def family(name):
    suffix = PurePosixPath(name).suffix.lower().lstrip(".")
    for label, extensions in (
        ("word", {"docx"}), ("excel", {"xlsx"}), ("powerpoint", {"pptx"}),
        ("pdf", {"pdf"}), ("image", {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp"}),
        ("text", {"txt", "md", "csv", "tsv", "json", "xml"}),
    ):
        if suffix in extensions:
            return label
    return "other"


def private_file_sink(destination):
    """Create once outside this checkout; caller verifies existing directory access.

    Inherited Windows ACLs are not established or expanded by this function.
    File writes are diagnostic evidence only, never Microsoft 365/business writes.
    """
    path = Path(destination).resolve()
    if (path.is_relative_to(ROOT) or any((parent / ".git").exists() for parent in path.parents)
            or not path.parent.is_dir() or path.exists() or path.suffix != ".json"):
        raise DiagnosticFailure("RECEIPT_RETENTION_FAILED")

    def retain(payload):
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        return path.read_bytes()

    return retain


def diagnose(intake, *, source_commit, image_digest, execution_id, retain,
             subtree="pending", listing_limit=500, sample_limit=50,
             now=utc_now, clock=time.monotonic):
    """Return aggregates only after exact restricted readback; failures also fail closed.

    Image identity is an operator pin requiring independent Azure verification.
    The local module/method fingerprints are checked here. Time is checked between
    operations; a listing request already in flight retains the intake timeout.
    """
    import re

    if (type(source_commit) is not str or source_commit not in PINS or image_digest != PINS[source_commit][2]
            or type(subtree) is not str or subtree not in {"pending", "processed"}
            or type(listing_limit) is not int or not 1 <= listing_limit <= 500
            or type(sample_limit) is not int or not 1 <= sample_limit <= 50
            or type(execution_id) is not str
            or not re.fullmatch(r"(?:run-[0-9]+-attempt-[1-9][0-9]*|manual-[a-f0-9-]{36})", execution_id)
            or not callable(retain)):
        raise DiagnosticFailure("INVALID_CONFIGURATION")
    started = clock()
    receipt = {
        "diagnostic_version": VERSION, "source_commit": source_commit,
        "image_digest_operator_pin": image_digest, "image_independently_attested_by_tool": False,
        "execution_id": execution_id, "subtree": subtree, "listing_limit": listing_limit,
        "sample_limit": sample_limit, "started_at_utc": now(), "listing_completed_at_utc": None,
        "between_operation_time_limit_seconds": 45, "metadata_timeout_seconds": 8,
        "status": "failed", "code": "SOURCE_INCOMPATIBLE", "listed_count": 0,
        "failure_stage": "source_compatibility", "cleanup": "no_temporary_cloud_resource_created",
        "selected_count": 0, "compared_count": 0, "observations": [],
        "content_downloads": 0, "business_writes": 0,
    }
    code = "SOURCE_INCOMPATIBLE"
    secret = secrets.token_bytes(32)  # Never persisted; references cannot correlate across runs.
    try:
        if fingerprint(intake) != PINS[source_commit][:2]:
            raise DiagnosticFailure("SOURCE_INCOMPATIBLE")
        if subtree == "processed" and not PINS[source_commit][3]:
            raise DiagnosticFailure("ARCHIVE_BOUND_UNSUPPORTED")
        code = "LISTING_FAILED"
        receipt["failure_stage"] = "listing"
        rows = intake.list_files(**{subtree + "_only": True}, max_files=listing_limit)
        if not isinstance(rows, list) or len(rows) > listing_limit:
            raise DiagnosticFailure("LISTING_FAILED")
        receipt["listing_completed_at_utc"] = now()
        receipt["listed_count"] = len(rows)
        if not rows:
            raise DiagnosticFailure("NO_ITEMS")
        ordered = sorted(rows, key=lambda row: (row["size"] == 0, row["size"], row["id"]))
        if subtree == "processed":
            samples = {}
            for row in ordered:
                kind = family(str(row["name"]))
                if row["size"] > 0 and kind != "other":
                    samples.setdefault(kind, row)
            ordered = [samples[k] for k in sorted(samples)] or ordered[:1]
        selected = ordered[:sample_limit]
        receipt["selected_count"] = len(selected)
        code = "COMPLETE"
        for row in selected:
            if clock() - started >= 45:
                receipt["failure_stage"] = "time_bound"
                raise DiagnosticFailure("TIME_BOUND_REACHED")
            code_before_request = code
            code = "METADATA_FAILED"
            receipt["failure_stage"] = "metadata"
            item_id = str(row["id"])
            observed = {
                "candidate_ref": hmac.new(secret, (intake.config.drive_id + "|" + item_id).encode(), hashlib.sha256).hexdigest(),
                "family": family(str(row["name"])), "observed_at_utc": now(),
                "http_status": None, "mismatches": None,
            }
            receipt["observations"].append(observed)
            response = intake.client.get(
                f"{GRAPH_ROOT}/drives/{intake.config.drive_id}/items/{item_id}",
                headers=intake._headers(), params={"$select": "id,name,size,eTag,parentReference,file"},
                timeout=8.0,
            )
            status = response.status_code
            if type(status) is not int or not 100 <= status <= 599:
                raise DiagnosticFailure("METADATA_FAILED")
            observed["http_status"] = status
            observed["observed_at_utc"] = now()
            if status != 200:
                raise DiagnosticFailure("METADATA_FAILED")
            current = response.json()
            receipt["failure_stage"] = "comparison"
            flags = {
                "id": current.get("id") != item_id,
                "name": current.get("name") != row["name"],
                "etag": current.get("eTag") != row["etag"],
                "size": current.get("size") != row["size"],
                "parent_boundary": (current.get("parentReference") or {}).get("id") not in intake._listed_folder_ids,
                "listed_snapshot": intake._listed_items.get(item_id) != row,
            }
            observed["mismatches"] = flags
            receipt["compared_count"] += 1
            code = "CONSISTENCY_MISMATCH" if any(flags.values()) else code_before_request
        if clock() - started >= 45:
            receipt["failure_stage"] = "time_bound"
            raise DiagnosticFailure("TIME_BOUND_REACHED")
    except DiagnosticFailure as error:
        code = str(error)
    except Exception:
        # The fixed stage code is the only exception information retained.
        if code not in {"SOURCE_INCOMPATIBLE", "LISTING_FAILED", "METADATA_FAILED"}:
            code = "METADATA_FAILED"
    receipt["code"] = code
    receipt["status"] = "complete" if code == "COMPLETE" else "failed"
    if code == "COMPLETE":
        receipt["failure_stage"] = None
    receipt["finished_at_utc"] = now()
    payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n").encode()
    public = {"diagnostic_version": VERSION, "status": receipt["status"], "code": code,
              "listed_count": receipt["listed_count"], "selected_count": receipt["selected_count"],
              "compared_count": receipt["compared_count"],
              "mismatch_counts": {key: sum(bool((r["mismatches"] or {}).get(key)) for r in receipt["observations"]) for key in KEYS},
              "content_downloads": 0, "business_writes": 0}
    try:
        readback = retain(payload)
        if not isinstance(readback, bytes) or not hmac.compare_digest(readback, payload):
            raise ValueError
    except Exception:
        raise DiagnosticFailure("RECEIPT_RETENTION_FAILED") from None
    if code != "COMPLETE":
        raise DiagnosticFailure(code, public) from None
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--image-digest", required=True)
    parser.add_argument("--execution-id", required=True)
    parser.add_argument("--subtree", choices=("pending", "processed"), default="pending")
    args = parser.parse_args(argv)
    intake = None
    exit_code = 0
    try:
        retain = private_file_sink(args.receipt)
        from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake
        intake = GovernedM365Intake(GovernedM365Config.from_environment())
        result = diagnose(intake, source_commit=args.source_commit, image_digest=args.image_digest,
                          execution_id=args.execution_id, subtree=args.subtree, retain=retain)
    except DiagnosticFailure as error:
        result = error.summary
        exit_code = 1
    except Exception:
        result = {"diagnostic_version": VERSION, "status": "failed", "code": "INVALID_CONFIGURATION"}
        exit_code = 1
    finally:
        if intake is not None:
            try:
                intake.client.close()
            except Exception:
                result = {"diagnostic_version": VERSION, "status": "failed", "code": "CLIENT_CLEANUP_FAILED"}
                exit_code = 1
    print(json.dumps(result, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
