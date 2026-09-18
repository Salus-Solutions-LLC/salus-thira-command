"""Live, isolated acceptance for released-report storage in Microsoft 365.

The script uses an ephemeral SQLite database inside the running Container App,
while retaining its real managed identity and folder-scoped Graph configuration.
It leaves one clearly identified acceptance artifact in the generated-report
folder and does not modify the operational PostgreSQL database.
"""

from __future__ import annotations

import json
import os
from pathlib import Path


def configure_isolated_runtime() -> None:
    database = Path("/tmp/salcapa-m365-report-acceptance.db")
    database.unlink(missing_ok=True)
    os.environ.update(
        {
            "SALUS_AUTH_MODE": "prototype",
            "SALUS_DB_BACKEND": "sqlite",
            "SALUS_DB_PATH": str(database),
            "SALUS_ALLOW_SQLITE_PRODUCTION": "1",
            "SALUS_SEED_DEMO": "1",
            "SALUS_STORAGE_BACKEND": "local",
            "SALUS_LOCAL_STORAGE_DIR": "/tmp/salcapa-m365-report-acceptance-storage",
        }
    )


def expect(response, status: int):
    if response.status_code != status:
        raise AssertionError(
            f"{response.request.method} {response.request.url.path}: "
            f"expected {status}, received {response.status_code}: {response.text[:500]}"
        )
    return response.json() if response.content else None


def main() -> None:
    configure_isolated_runtime()

    from fastapi.testclient import TestClient
    import app

    client = TestClient(app.app)
    admin = {
        "X-Salus-Tenant": "1",
        "X-Salus-Role": "System Administrator",
        "X-Salus-User": "M365 Acceptance Administrator",
    }
    reviewer = {
        **admin,
        "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "M365 Acceptance Reviewer",
    }
    member = {
        "X-Salus-Tenant": "1",
        "X-Salus-Role": "Client Executive",
        "X-Salus-User": "M365 Acceptance Protected Member",
    }
    other_tenant = {
        **member,
        "X-Salus-Tenant": "2",
        "X-Salus-User": "Cross-tenant Acceptance User",
    }

    assessment_payload = {
        "name": "MICROSOFT 365 LIVE ACCEPTANCE — SAFE TO RETAIN",
        "organization": "Salus Solutions",
        "assessment_type": "Enterprise",
        "purpose": "Verify governed SharePoint report publication and retrieval.",
        "mission": "Validate the released-report storage boundary.",
        "scope": "Isolated acceptance database and dedicated generated-report folder.",
        "exclusions": "Operational assessment records.",
        "executive_sponsor": "",
        "assessment_director": "",
        "lead_assessor": "",
        "start_date": "",
        "target_completion": "",
        "reassessment_date": "",
        "classification": "Standard",
    }
    assessment = expect(client.post("/api/assessments", headers=admin, json=assessment_payload), 200)
    report = expect(client.post(f"/api/reports/{assessment['id']}", headers=admin, json={}), 200)
    report_id = report["id"]

    # Protected Members cannot see drafts.
    expect(client.get(f"/api/integrations/m365/reports/versions/{report_id}", headers=member), 404)

    for status, headers in (
        ("Reviewed", reviewer),
        ("Approved", admin),
        ("Released", admin),
    ):
        report = expect(
            client.post(
                f"/api/reports/versions/{report_id}/transition",
                headers=headers,
                json={"status": status, "reason": "Governed Microsoft 365 live acceptance."},
            ),
            200,
        )

    # Read the real SharePoint artifact through the Protected Member boundary.
    stored = expect(
        client.get(f"/api/integrations/m365/reports/versions/{report_id}", headers=member),
        200,
    )
    if stored.get("assessment", {}).get("name") != assessment_payload["name"]:
        raise AssertionError("Stored member-safe report does not match the acceptance assessment")

    # The same identifier must not cross a tenant boundary.
    expect(
        client.get(f"/api/integrations/m365/reports/versions/{report_id}", headers=other_tenant),
        404,
    )

    status = expect(client.get("/api/integrations/m365/reports/status", headers=admin), 200)
    if not status.get("configured") or status.get("mode") != "folder_selected":
        raise AssertionError("Microsoft 365 report storage did not report folder-scoped readiness")

    print(
        json.dumps(
            {
                "result": "SALCAPA_M365_REPORT_LIVE_ACCEPTANCE_PASS",
                "assessment_id": assessment["id"],
                "report_id": report_id,
                "report_status": report["status"],
                "member_retrieval": "passed",
                "draft_denial": "passed",
                "cross_tenant_denial": "passed",
                "storage_mode": status["mode"],
                "artifact_sha256": report["snapshot_sha256"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
