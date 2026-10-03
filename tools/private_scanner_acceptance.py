"""PRIVATE, FICTIONAL scanner acceptance candidate. Never run as the web app.

This script is source for a separately reviewed, manually triggered Container App
job. It exercises the real package file route and quarantine writer, then waits
for the already deployed Defender/Event Grid/result worker to decide each file.
It deliberately bypasses quote/acceptance *only in this private job process* by
creating clearly labelled test fixtures. It cannot establish commercial, OIDC,
Stripe, authority, agreement-scan, or public Member acceptance.

Do not execute before the exact source, Azure template, identity, cost, records,
and live-output reviews required by the Salus Program Charter.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone


def guarded_environment() -> None:
    required = {
        "SALUS_ACCEPTANCE_PRIVATE_JOB": "1",
        "SALUS_AUTH_MODE": "session",
        "SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED": "1",
        "SALUS_PACKAGE_SCAN_MODE": "defender",
        "SALUS_ENV": "dev",
        "SALUS_DB_BACKEND": "postgres",
    }
    for name, value in required.items():
        if os.getenv(name, "").strip().lower() != value:
            raise RuntimeError(f"Private scanner acceptance requires {name}={value}.")
    if not os.getenv("AZURE_CLIENT_ID") or not os.getenv("SALUS_SCAN_QUARANTINE_URL"):
        raise RuntimeError("The private job needs its reviewed writer identity and quarantine URL.")
    if os.getenv("SALUS_ACCEPTANCE_JOB_NAME", "") != "salcapa-dev-b48224-scan-acceptance":
        raise RuntimeError("The private job identity is not the reviewed acceptance job.")
    if os.getenv("SALUS_ACCEPTANCE_EXPECTED_QUARANTINE_URL") != os.getenv("SALUS_SCAN_QUARANTINE_URL"):
        raise RuntimeError("The quarantine URL differs from the reviewed target.")


def _insert(conn, table: str, values: dict) -> int:
    # Table and column names are fixed in source, never supplied by a caller.
    fields = ",".join(values)
    marks = ",".join("?" for _ in values)
    cur = conn.execute(f"INSERT INTO {table} ({fields}) VALUES ({marks})", tuple(values.values()))
    return int(cur.lastrowid)


def seed_fictional_scope(app, run_id: str):
    """Create isolated fixture IDs; no real agreement, quote or payment is asserted."""
    if not re.fullmatch(r"[a-z0-9]{8,24}", run_id):
        raise ValueError("run ID must be 8–24 lowercase letters or digits")
    slug = "fictional-scanner-" + run_id
    stamp = app.now()
    conn = app.db()
    try:
        if conn.execute("SELECT 1 FROM tenants WHERE slug=?", (slug,)).fetchone():
            raise RuntimeError("Acceptance run ID already exists; never reuse test records.")
        tenant_id = _insert(conn, "tenants", {
            "name": "FICTIONAL scanner acceptance — no Protected Member",
            "slug": slug, "status": "Test", "created_at": stamp,
        })
        user_id = _insert(conn, "users", {
            "tenant_id": tenant_id, "username": slug + "-decision-owner",
            "display_name": "FICTIONAL scanner test decision owner",
            "role": "Client Executive", "status": "Active",
            "created_at": stamp, "updated_at": stamp,
        })
        cookie = secrets.token_urlsafe(48)
        expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).replace(
            microsecond=0).isoformat().replace("+00:00", "Z")
        _insert(conn, "auth_sessions", {
            "user_id": user_id, "token_hash": app._hash_token(cookie),
            "expires_at": expires, "created_at": stamp, "last_seen_at": stamp,
        })
        assessment_id = _insert(conn, "assessments", {
            "tenant_id": tenant_id, "name": "FICTIONAL scanner acceptance " + run_id,
            "organization": "FICTIONAL TEST ONLY", "covered_operation": "Scanner acceptance",
            "exclusions": "No Protected Member work; no quote, purchase, or report",
            "requested_package_level": 1, "requested_scope_band": "A",
            "requested_access_variant": "Access", "status": "Test",
            "created_at": stamp, "updated_at": stamp,
        })
        fixture_digest = hashlib.sha256(("fictional-fixture-" + run_id).encode()).hexdigest()
        agreement_id = _insert(conn, "package_agreement_artifacts", {
            "tenant_id": tenant_id, "assessment_id": assessment_id,
            "original_name": "TEST ONLY — no agreement.pdf",
            "stored_name": f"tenant-{tenant_id}/test-only/{run_id}/no-agreement",
            "content_sha256": fixture_digest, "size_bytes": 1,
            "scan_status": "TestFixtureNotClean", "uploaded_by": "private-scanner-acceptance",
            "uploaded_at": stamp,
        })
        quote_id = _insert(conn, "package_quote_versions", {
            "tenant_id": tenant_id, "assessment_id": assessment_id,
            "version_no": 1, "assessment_version": 1, "level": 1,
            "band": "A", "variant": "Access", "covered_operation": "TEST ONLY",
            "exclusions": "No commercial authority", "scope_basis": "Scanner fixture only",
            "decision_owner": "FICTIONAL", "fee_cents": 1, "currency": "USD",
            "valid_until": "1900-01-01", "capacity_confirmed": 0,
            "access_eligibility_confirmed": 0, "agreement_artifact_id": agreement_id,
            "agreement_reference": "TEST ONLY — NOT AN AGREEMENT",
            "agreement_sha256": fixture_digest, "separate_services_excluded": 1,
            "content_sha256": "0" * 64, "approved_by": "NOT APPROVED — TEST FIXTURE",
            "approved_at": stamp,
        })
        item_id = _insert(conn, "package_intake_requests", {
            "tenant_id": tenant_id, "assessment_id": assessment_id,
            "quote_id": quote_id, "item_key": "GOV", "catalog_version": "test-only",
            "title": "FICTIONAL scanner test input", "decision_use": "Scanner acceptance only",
            "requested_form": "text", "acceptable_equivalent": "none",
            "request_reason": "Fictional scanner acceptance; no Member decision",
            "status": "Requested", "requested_by": "private-scanner-acceptance",
            "requested_at": stamp,
        })
        conn.commit()
        return tenant_id, user_id, assessment_id, quote_id, item_id, cookie
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _test_files(run_id: str):
    clean = ("SALUS FICTIONAL CLEAN SCANNER TEST " + run_id).encode()
    # Construct the harmless EICAR industry test string only at runtime.
    eicar = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" +
             "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode("ascii")
    return (("clean", clean), ("eicar", eicar))


def run(run_id: str, timeout_seconds: int):
    guarded_environment()  # Must happen before importing app or opening its database.
    import app
    from fastapi.testclient import TestClient

    if app.ENVIRONMENT != "dev" or app.AUTH_MODE != "session" or app.PACKAGE_SCAN_MODE != "defender":
        raise RuntimeError("The imported application differs from the reviewed private-job mode.")
    tenant_id, user_id, assessment_id, quote_id, item_id, cookie = seed_fictional_scope(app, run_id)
    normal_authorizer = app.authorized_package_intake

    def fixture_authorizer(conn, requested_assessment_id, request):
        if (requested_assessment_id != assessment_id or app.tenant_id(request) != tenant_id
                or app.auth_context(request).get("user_id") != user_id):
            raise RuntimeError("The private fixture cannot authorize another scope.")
        row = conn.execute("SELECT id FROM package_quote_versions WHERE id=? AND tenant_id=? AND assessment_id=?",
                           (quote_id, tenant_id, assessment_id)).fetchone()
        if not row:
            raise RuntimeError("The fictional quote fixture is missing.")
        return row

    app.authorized_package_intake = fixture_authorizer
    client = TestClient(app.app, cookies={"salus_session": cookie})
    staged = []
    try:
        for label, payload in _test_files(run_id):
            response = client.post(
                f"/api/assessments/{assessment_id}/package-intake/{item_id}/files",
                files={"file": (label + ".txt", payload, "text/plain")},
            )
            if response.status_code != 200 or response.json().get("scan_status") != "Pending":
                raise RuntimeError(f"{label} was not held Pending by the application route.")
            pending_id = int(response.json()["id"])
            conn = app.db()
            try:
                row = conn.execute("SELECT * FROM package_intake_pending_scans WHERE id=? AND tenant_id=?",
                                   (pending_id, tenant_id)).fetchone()
                if not row or row["content_sha256"] != hashlib.sha256(payload).hexdigest():
                    raise RuntimeError(f"{label} has no exact pending manifest.")
                staged.append((label, pending_id, row["blob_version_id"], row["etag"], row["blob_uri"]))
            finally:
                conn.close()
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            conn = app.db()
            try:
                rows = [conn.execute("SELECT status,scan_result,promoted_upload_id,scan_event_id FROM package_intake_pending_scans WHERE id=? AND tenant_id=?",
                                     (pending_id, tenant_id)).fetchone() for _, pending_id, *_ in staged]
            finally:
                conn.close()
            if all(row and row["status"] in ("Promoted", "Malicious", "Unscanned", "Reconcile") for row in rows):
                break
            time.sleep(10)
        else:
            raise RuntimeError("Defender/result-worker acceptance timed out; originals remain held.")
        outcomes = {label: dict(row) for (label, *_), row in zip(staged, rows)}
        if outcomes["clean"]["status"] != "Promoted" or outcomes["clean"]["scan_result"] != "Clean":
            raise RuntimeError("Clean original was not promoted after a real scanner result.")
        if (outcomes["eicar"]["status"] != "Malicious"
                or outcomes["eicar"]["scan_result"] != "Malicious"
                or outcomes["eicar"]["promoted_upload_id"]):
            raise RuntimeError("EICAR was not detected as Malicious and held by the real scanner.")
        if (not outcomes["clean"]["scan_event_id"] or not outcomes["eicar"]["scan_event_id"]
                or outcomes["clean"]["scan_event_id"] == outcomes["eicar"]["scan_event_id"]):
            raise RuntimeError("Distinct Defender result event IDs were not recorded.")
        conn = app.db()
        try:
            clean_upload = conn.execute(
                "SELECT stored_name,content_sha256,scan_status FROM package_intake_uploads "
                "WHERE id=? AND tenant_id=? AND assessment_id=?",
                (outcomes["clean"]["promoted_upload_id"], tenant_id, assessment_id),
            ).fetchone()
            adverse_count = conn.execute(
                "SELECT COUNT(*) AS n FROM package_intake_uploads WHERE tenant_id=? "
                "AND assessment_id=? AND content_sha256=?",
                (tenant_id, assessment_id, hashlib.sha256(dict(_test_files(run_id))["eicar"]).hexdigest()),
            ).fetchone()["n"]
        finally:
            conn.close()
        clean_digest = hashlib.sha256(dict(_test_files(run_id))["clean"]).hexdigest()
        if (not clean_upload or clean_upload["scan_status"] != "Clean"
                or clean_upload["content_sha256"] != clean_digest
                or hashlib.sha256(app.storage.get_bytes(clean_upload["stored_name"])).hexdigest() != clean_digest):
            raise RuntimeError("Promoted Clean evidence failed independent read-after-write integrity.")
        if adverse_count:
            raise RuntimeError("A malicious test original was copied to promoted evidence.")
        # Only opaque IDs/statuses leave the job. Full object evidence stays in governed records.
        print(json.dumps({"acceptance_run": run_id, "tenant_id": tenant_id,
                          "assessment_id": assessment_id,
                          "clean_pending_id": staged[0][1], "clean_status": outcomes["clean"]["status"],
                          "adverse_pending_id": staged[1][1], "adverse_status": outcomes["eicar"]["status"],
                          "scope": "scanner only; commercial/OIDC/payment/alert gates still open"}, sort_keys=True))
    finally:
        app.authorized_package_intake = normal_authorizer
        client.close()
        # Do not leave a reusable fictional sign-in after the private run.
        conn = app.db()
        try:
            conn.execute("DELETE FROM auth_sessions WHERE user_id=? AND token_hash=?",
                         (user_id, app._hash_token(cookie)))
            conn.commit()
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", default="", help="unique fictional ID; generated when omitted")
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    if not args.execute:
        raise SystemExit("Candidate only. Exact source and Azure reviews are required before --execute.")
    if not 60 <= args.timeout_seconds <= 1200:
        raise SystemExit("Timeout must be between 60 and 1200 seconds.")
    run(args.run_id or secrets.token_hex(8), args.timeout_seconds)


if __name__ == "__main__":
    main()

