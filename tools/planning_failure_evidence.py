"""Retain bounded audit evidence without exporting source content or config values."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def marker_evidence(text):
    records, conflicts, rejected = {}, set(), 0
    for line in text.splitlines():
        match = re.search(r"\b(TASK_KNOWLEDGE_[A-Z0-9_]+)=([^\s]+)", line)
        if not match:
            continue
        key, value = match.groups()
        suffix = key.removeprefix("TASK_KNOWLEDGE_")
        if suffix.endswith("SHA256") or suffix in {"PROTECTED_CONTROLS_BEFORE", "PROTECTED_CONTROLS_AFTER"}:
            valid = re.fullmatch(r"[0-9a-f]{64}", value)
        elif re.fullmatch(r"Q[1-4]_RECEIPT_ID", suffix):
            valid = re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value)
        elif suffix == "FAILURE_TYPE":
            valid = value in {"RuntimeError", "ValueError", "KeyError", "TypeError", "AssertionError", "OperationalError", "DatabaseError"}
        elif suffix == "FAILURE_STAGE":
            valid = value in {"not_started", "connect_database", "initialize_scoped_source_client", "represented_precheck", "duplicate_receipt_precheck", "source_census", "membership_prequery", "create_receipt", "verify_durable_receipt", "membership_postquery", "source_census_readback"}
        else:
            valid = re.fullmatch(r"[0-9]{1,12}", value)
        if not valid:
            rejected += 1
            continue
        if key in records and records[key] != value:
            conflicts.add(key)
        records[key] = value
    return {"schema_version": 1, "records": records, "conflicting_keys": sorted(conflicts),
            "rejected_marker_count": rejected,
            "limit": "Filtered telemetry only. This collector does not validate receipt completeness or grant acceptance."}


def projection(resource):
    if not isinstance(resource, dict) or not isinstance(resource.get("properties"), dict):
        raise ValueError("Resource shape unavailable")
    properties = resource["properties"]
    if "identity" not in resource or any(key not in properties for key in ("template", "configuration")):
        raise ValueError("Required configuration projection unavailable")
    return {"identity": resource["identity"], "template": properties["template"],
            "configuration": properties["configuration"]}


def named_array_order(value):
    """Diagnostic only; never used to make the strict acceptance decision."""
    if isinstance(value, dict):
        return {key: named_array_order(item) for key, item in value.items()}
    if isinstance(value, list):
        items = [named_array_order(item) for item in value]
        if items and all(isinstance(item, dict) and isinstance(item.get("name"), str) for item in items):
            names = [item["name"] for item in items]
            if len(set(names)) == len(names):
                items.sort(key=lambda item: item["name"])
        return items
    return value


def configuration_evidence(before, after):
    before, after = projection(before), projection(after)
    equal = before == after
    return {"schema_version": 1, "strict_equal": equal,
            "before_sha256": digest(before), "after_sha256": digest(after),
            "differing_sections": [key for key in before if before[key] != after[key]],
            "named_array_order_only": not equal and named_array_order(before) == named_array_order(after),
            "limit": "Strict equality remains required. Named-array sorting is diagnostic only. No configuration values or names are exported."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("markers", "configuration"))
    parser.add_argument("--input", required=True)
    parser.add_argument("--after")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        before = Path(args.input).read_text(encoding="utf-8")
        if args.mode == "markers":
            evidence = marker_evidence(before)
            evidence["input_present"] = True
            success = bool(evidence["records"]) and not evidence["conflicting_keys"] and evidence["rejected_marker_count"] == 0
        else:
            evidence = configuration_evidence(json.loads(before), json.loads(Path(args.after).read_text(encoding="utf-8")))
            success = evidence["strict_equal"]
    except (OSError, ValueError, TypeError):
        evidence = {"schema_version": 1, "state": "input_unavailable_or_invalid", "accepted": False}
        success = False
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    if args.mode == "markers":
        for key, value in sorted(evidence.get("records", {}).items()):
            print(f"{key}={value}", flush=True)
    raise SystemExit(0 if success else 1)


if __name__ == "__main__":
    main()
