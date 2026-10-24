"""One reviewed, private EICAR upload to the existing fictional Level 1A order.

This source is sent as the command of one protected manual Azure job execution.
It is not a web route, a buyer sign-in, a payment, or a general test fixture.
The job definition is left unchanged. Never run it from a workstation.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time


ORDER_ID = 10
BUYER_EMAIL = "mduncan@salus.solutions"
BUYER_NAME = "Fictional Cedar Works LLC"
UNIT_NAME = "Fictional Cedar Site"
ITEM_TITLE = "Leadership priorities and constraints"
FILE_NAME = "salus-level1a-eicar-test.txt"


def _require_private_environment() -> None:
    required = {
        "SALUS_ACCEPTANCE_PRIVATE_JOB": "1",
        "SALUS_ACCEPTANCE_JOB_NAME": "salcapa-dev-b48224-scan-test",
        "SALUS_ENV": "dev",
        "SALUS_AUTH_MODE": "session",
        "SALUS_DB_BACKEND": "postgres",
        "SALUS_STORAGE_BACKEND": "azure",
        "SALUS_PACKAGE_SCAN_MODE": "defender",
        "SALUS_AZURE_STORAGE_CONTAINER": "evidence",
    }
    if any(os.environ.get(key) != value for key, value in required.items()):
        raise RuntimeError("private_environment_mismatch")
    if (not os.environ.get("AZURE_CLIENT_ID") or
            not os.environ.get("SALUS_POSTGRES_HOST", "").startswith("salcapa-dev-b48224-pg.") or
            os.environ.get("SALUS_ACCEPTANCE_EXPECTED_QUARANTINE_URL") !=
            os.environ.get("SALUS_SCAN_QUARANTINE_URL") or
            not os.environ.get("SALUS_SCAN_QUARANTINE_URL", "").startswith(
                "https://salcapadevb48224scan.blob.core.windows.net/")):
        raise RuntimeError("private_target_mismatch")


def _target(conn, app, payload_sha256: str) -> dict:
    order = conn.execute("""SELECT o.*,u.email,u.identity_provider FROM level1a_orders o
        JOIN users u ON u.id=o.buyer_user_id AND u.tenant_id=o.tenant_id
        WHERE o.id=?""", (ORDER_ID,)).fetchone()
    if (not order or str(order["email"] or "").casefold() != BUYER_EMAIL or
            order["identity_provider"] != app.CUSTOMER_PROVIDER or
            order["buyer_legal_name"] != BUYER_NAME or
            order["unit_name"] != UNIT_NAME):
        raise RuntimeError("fictional_order_mismatch")
    tenant_id = int(order["tenant_id"])
    user_id = int(order["buyer_user_id"])
    # This validates the original Stripe sandbox payment, exact binding and
    # immutable receipt. It creates no second payment or order.
    original_intake = app.LEVEL1A_INTAKE_ENABLED
    app.LEVEL1A_INTAKE_ENABLED = True  # This private process has no ingress.
    try:
        binding, _ = app._paid_level1a_intake(conn, ORDER_ID, tenant_id, user_id)
    finally:
        app.LEVEL1A_INTAKE_ENABLED = original_intake
    link = conn.execute("""SELECT assessment_id FROM level1a_assessment_links
        WHERE order_id=? AND tenant_id=? AND buyer_user_id=? AND scope_sha256=?""",
        (ORDER_ID, tenant_id, user_id, binding.scope_sha256)).fetchone()
    item = conn.execute("""SELECT id,assessment_id,status FROM level1a_intake_items
        WHERE order_id=? AND tenant_id=? AND title=?""",
        (ORDER_ID, tenant_id, ITEM_TITLE)).fetchone()
    authority = conn.execute("""SELECT 1 FROM level1a_disclosure_authority
        WHERE order_id=? AND tenant_id=? AND buyer_user_id=? AND scope_sha256=?
        AND statement_version=?""",
        (ORDER_ID, tenant_id, user_id, binding.scope_sha256,
         app.DISCLOSURE_STATEMENT_VERSION)).fetchone()
    if (not link or not item or item["assessment_id"] != link["assessment_id"] or
            item["status"] != "Requested" or not authority):
        raise RuntimeError("intake_scope_mismatch")
    existing = conn.execute("""SELECT
        (SELECT COUNT(*) FROM level1a_pending_scans
            WHERE tenant_id=? AND intake_request_id=?) +
        (SELECT COUNT(*) FROM level1a_intake_uploads
            WHERE tenant_id=? AND intake_request_id=?) AS n""",
        (tenant_id, item["id"], tenant_id, item["id"])).fetchone()
    if int(existing["n"]) != 0:
        raise RuntimeError("target_item_already_has_file")
    duplicate = conn.execute("""SELECT 1 FROM level1a_pending_scans
        WHERE tenant_id=? AND order_id=? AND content_sha256=?""",
        (tenant_id, ORDER_ID, payload_sha256)).fetchone()
    if duplicate:
        raise RuntimeError("adverse_sample_already_staged")
    return {"tenant_id": tenant_id, "user_id": user_id,
            "assessment_id": int(link["assessment_id"]),
            "item_id": int(item["id"])}


def _eicar() -> bytes:
    # Construct only in the private Azure job; local Defender correctly blocked
    # a workstation file before transmission.
    data = ("X5O!P%@AP[4\\PZX54(P^)7CC)7}$" +
            "EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*").encode("ascii")
    if len(data) != 68:
        raise RuntimeError("sample_length_mismatch")
    return data


def run() -> None:
    _require_private_environment()  # Check before importing the application.
    import app
    from fastapi.testclient import TestClient

    if (app.ENVIRONMENT != "dev" or app.DB_BACKEND != "postgres" or
            app.STORAGE_BACKEND != "azure" or app.PACKAGE_SCAN_MODE != "defender"):
        raise RuntimeError("application_mode_mismatch")
    payload = _eicar()
    digest = hashlib.sha256(payload).hexdigest()
    conn = app.db()
    try:
        target = _target(conn, app, digest)
    finally:
        conn.close()

    # Route through the actual Level 1A upload handler in this no-ingress job.
    # Only its buyer-context lookup is substituted, after the exact paid order,
    # Microsoft buyer, disclosure authority and empty target item were checked.
    original_authority = app._level1a_draft_authority
    original_upload = app.LEVEL1A_UPLOAD_ENABLED
    original_scanner = app.PACKAGE_SCANNER_ACCEPTED
    original_intake = app.LEVEL1A_INTAKE_ENABLED
    app.LEVEL1A_INTAKE_ENABLED = True
    app.LEVEL1A_UPLOAD_ENABLED = True
    app.PACKAGE_SCANNER_ACCEPTED = True

    def private_authority(request):
        if request.url.path != (
            f"/api/level1a/orders/{ORDER_ID}/intake/{target['item_id']}/files"
        ):
            raise RuntimeError("private_route_mismatch")
        return {"tenant_id": target["tenant_id"],
                "user_id": target["user_id"],
                "user": "private-level1a-adverse-acceptance"}

    app._level1a_draft_authority = private_authority
    try:
        client = TestClient(app.app)
        try:
            response = client.post(
                f"/api/level1a/orders/{ORDER_ID}/intake/{target['item_id']}/files",
                files={"file": (FILE_NAME, payload, "text/plain")},
            )
        finally:
            client.close()
        if response.status_code != 200:
            raise RuntimeError("upload_route_rejected_sample")
        result = response.json()
        if (result.get("scan_status") != "Pending" or
                result.get("idempotent") is not False or
                type(result.get("id")) is not int):
            raise RuntimeError("new_pending_manifest_missing")
        pending_id = result["id"]
    finally:
        app._level1a_draft_authority = original_authority
        app.LEVEL1A_UPLOAD_ENABLED = original_upload
        app.PACKAGE_SCANNER_ACCEPTED = original_scanner
        app.LEVEL1A_INTAKE_ENABLED = original_intake

    deadline = time.monotonic() + 900
    while time.monotonic() < deadline:
        conn = app.db()
        try:
            pending = conn.execute("""SELECT status,scan_result,scan_event_id,
                promoted_upload_id,content_sha256 FROM level1a_pending_scans
                WHERE id=? AND tenant_id=? AND order_id=? AND assessment_id=?
                AND intake_request_id=?""",
                (pending_id, target["tenant_id"], ORDER_ID,
                 target["assessment_id"], target["item_id"])).fetchone()
            promoted = conn.execute("""SELECT COUNT(*) AS n FROM level1a_intake_uploads
                WHERE tenant_id=? AND order_id=? AND intake_request_id=?
                AND content_sha256=?""",
                (target["tenant_id"], ORDER_ID, target["item_id"], digest)).fetchone()
        finally:
            conn.close()
        if not pending or pending["content_sha256"] != digest:
            raise RuntimeError("exact_pending_manifest_lost")
        if pending["status"] in {"Malicious", "Unscanned", "Promoted", "Reconcile"}:
            break
        time.sleep(10)
    else:
        raise RuntimeError("defender_result_timeout_sample_remains_held")
    if (pending["status"] != "Malicious" or
            pending["scan_result"] != "Malicious" or
            not pending["scan_event_id"] or pending["promoted_upload_id"] or
            int(promoted["n"]) != 0):
        raise RuntimeError("adverse_result_not_held")
    print(json.dumps({"order_reference": "L1A-10",
                      "adverse_status": "Malicious",
                      "event_recorded": True,
                      "promoted_count": 0}, sort_keys=True))


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        # No source path, object ID, document content, or raw exception leaves
        # the private job log. A failed or timed-out sample remains held.
        print(json.dumps({"result": "failed", "failure_class": type(exc).__name__}))
        sys.exit(1)
