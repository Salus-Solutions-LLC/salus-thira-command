"""One-time governed disposition of four historical fictional scanner exceptions.

This code is injected only into a protected private inventory-job execution.
It never deletes a Blob, changes a hold, or grants customer access. Its output
contains counts and an error class, never object or tenant identifiers.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime, timezone

from salus_scan_inventory import compare_quarantine_versions, list_azure_quarantine_versions


EXPECTED_CLEANUP_NAMES = {
    "scanner-acceptance/clean-20261002-01.txt",
    "scanner-acceptance/eicar-20261002-01.txt",
}
PRIOR_EVIDENCE_RUN = "38425632390"


def qualify(rows: list[dict], ledger: list[dict], azure: list[dict],
            deleted: set[tuple[str, str]], account_url: str) -> dict[str, str]:
    """Return a reason for exactly four independently requalified records."""
    if max(len(rows), len(ledger), len(azure), len(deleted)) > 100:
        raise ValueError("Review capacity exceeded")
    comparison = compare_quarantine_versions(ledger, azure, max_versions=100)
    if any(comparison[field] for field in (
            "unlinked_versions", "missing_versions", "size_mismatches", "hold_mismatches")):
        raise ValueError("Current inventory differs")
    if len(rows) != 4 or len({row["exception_key"] for row in rows}) != 4:
        raise ValueError("Historical record set differs")
    current_ledger = {(row["blob_name"], row["blob_version_id"]): row for row in ledger}
    current_azure = {(row["name"], row["version_id"]): row for row in azure}
    unlinked_names = set()
    counts = {"Unlinked": 0, "HoldMismatch": 0}
    reasons = {}
    for row in rows:
        kind = row["exception_type"]
        if (kind not in counts or row["status"] != "Open"
                or row["account_url"] != account_url
                or row["assigned_to"] or row["disposition"]):
            raise ValueError("Historical record is outside the reviewed boundary")
        name, version = row["blob_name"], row["blob_version_id"]
        if not isinstance(name, str) or not name or not isinstance(version, str) or not version:
            raise ValueError("Historical version is incomplete")
        expected_key = hashlib.sha256(
            f"{account_url}\0{kind}\0{name}\0{version}".encode("utf-8")
        ).hexdigest()
        if row["exception_key"] != expected_key:
            raise ValueError("Historical record key differs")
        key = (name, version)
        if kind == "Unlinked":
            if (name not in EXPECTED_CLEANUP_NAMES or key not in deleted
                    or key in current_ledger or key in current_azure
                    or row["candidate_tenant_id"] is not None):
                raise ValueError("Fictional cleanup is not exact")
            unlinked_names.add(name)
            reasons[row["exception_key"]] = "Fictional test original: exact version is soft-deleted and absent from active inventory"
        else:
            recorded, stored = current_ledger.get(key), current_azure.get(key)
            if (recorded is None or stored is None
                    or row["candidate_tenant_id"] != recorded["tenant_id"]
                    or bool(recorded["legal_hold"]) != stored["legal_hold"]
                    or recorded["size_bytes"] != stored["size_bytes"]):
                raise ValueError("Historical hold mismatch is not reconciled")
            reasons[row["exception_key"]] = "Historical hold mismatch: current exact ledger and Azure version agree"
        counts[kind] += 1
    if counts != {"Unlinked": 2, "HoldMismatch": 2} or unlinked_names != EXPECTED_CLEANUP_NAMES:
        raise ValueError("Historical categories differ")
    return reasons


def main() -> None:
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f]{40}", sys.argv[1]):
        raise ValueError("Reviewed source commit is missing")
    from app import db, package_quarantine

    reader = package_quarantine(for_worker=True)
    conn = db()
    try:
        ledger = [dict(row) for row in conn.execute(
            "SELECT tenant_id,blob_name,blob_version_id,size_bytes,legal_hold "
            "FROM package_intake_pending_scans")]
        ledger.extend(dict(row) for row in conn.execute(
            "SELECT tenant_id,blob_name,blob_version_id,size_bytes,0 AS legal_hold "
            "FROM level1a_pending_scans"))
        rows = [dict(row) for row in conn.execute(
            "SELECT exception_key,account_url,exception_type,blob_name,blob_version_id,"
            "candidate_tenant_id,status,first_seen,last_seen,assigned_to,disposition "
            "FROM package_quarantine_inventory_exceptions WHERE status='Open'")]
        azure = list(list_azure_quarantine_versions(reader.container))
        deleted = set()
        listed = 0
        for blob in reader.container.list_blobs(include=["deleted", "versions", "deletedwithversions"]):
            listed += 1
            if listed > 100:
                raise ValueError("Azure listing exceeds review capacity")
            if (getattr(blob, "deleted", False) is True
                    and isinstance(blob.name, str) and blob.name
                    and isinstance(blob.version_id, str) and blob.version_id):
                deleted.add((blob.name, blob.version_id))
        reasons = qualify(rows, ledger, azure, deleted, reader.account_url)
        stamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        for row in rows:
            disposition = (
                f"{stamp}; {reasons[row['exception_key']]}; "
                f"evidence run {PRIOR_EVIDENCE_RUN}; reviewed source {sys.argv[1]}; "
                "qualified protected approval"
            )
            cursor = conn.execute(
                "UPDATE package_quarantine_inventory_exceptions "
                "SET status='Resolved',assigned_to='Salus qualified review',disposition=? "
                "WHERE exception_key=? AND status='Open' AND first_seen=? AND last_seen=? "
                "AND assigned_to='' AND disposition=''",
                (disposition, row["exception_key"], row["first_seen"], row["last_seen"]),
            )
            if cursor.rowcount != 1:
                raise ValueError("Historical record changed during review")
        remaining = conn.execute(
            "SELECT COUNT(*) AS n FROM package_quarantine_inventory_exceptions WHERE status='Open'"
        ).fetchone()["n"]
        if remaining:
            raise ValueError("Open historical records remain")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    print(json.dumps({"current_exceptions": 0, "historical_resolved": 4,
                      "historical_open": 0, "blob_changes": 0}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"historical_disposition": "failed",
                          "error_type": type(exc).__name__}, sort_keys=True))
        raise SystemExit(1)

