#!/usr/bin/env python3
"""Exercise the v3.111 report-release boundary on an isolated database copy.

This script is transported as hash-pinned, non-secret workflow input and runs
inside the exact frozen v3.111 image.  It must never target the accepted source
database or represent human review, approval, or release outside this bounded
acceptance exercise.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(os.environ.get("SALCAPA_ACCEPTANCE_ROOT", Path.cwd())).resolve()
sys.path.insert(0, str(ROOT))

import app as core
from salcapa_demo_fixtures import (
    DEMONSTRATION_ACKNOWLEDGEMENT,
    FIXTURE_AUTHORITY,
    register_demo_fixture_contract,
    seed_demo_environments,
)


def headers(tenant_id: int, role: str, user: str) -> dict[str, str]:
    return {
        "X-Salus-Tenant": str(tenant_id),
        "X-Salus-Role": role,
        "X-Salus-User": user,
    }


def main() -> None:
    assert core.APP_VERSION == "1.16.0"
    assert core.AUTH_MODE not in {"session", "oidc"}
    register_demo_fixture_contract(core)

    conn = core.db()
    try:
        seed_demo_environments(
            conn,
            environment="development",
            authority=FIXTURE_AUTHORITY,
            acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
            operation="seed",
            now=lambda: "10-09-2026 23:00:00 UTC",
        )
        fixture_tenants = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM tenants WHERE environment_kind='Fictional Demonstration' ORDER BY id"
            )
        ]
        assert len(fixture_tenants) == 3
        baseline = conn.execute(
            "SELECT id,tenant_id,mission FROM assessments "
            "WHERE tenant_id=? ORDER BY id LIMIT 1",
            (fixture_tenants[0],),
        ).fetchone()
        assert baseline is not None
        assessment_id = int(baseline["id"])
        tenant_id = int(baseline["tenant_id"])
        original_mission = str(baseline["mission"] or "")
    finally:
        conn.close()

    salus = headers(tenant_id, "SME Assessor", "isolated-report-preparer")
    member = headers(tenant_id, "Client Executive", "isolated-member-authority")
    viewer = headers(tenant_id, "Protected Member Viewer", "isolated-member-viewer")
    other = headers(fixture_tenants[1], "Client Executive", "isolated-other-member")
    client = TestClient(core.app)

    created = client.post(f"/api/reports/{assessment_id}", headers=salus, json={})
    assert created.status_code == 200, created.text
    report = created.json()
    report_id = int(report["id"])
    digest = str(report["snapshot_sha256"])
    snapshot_path = f"/api/reports/versions/{report_id}/snapshot"
    list_path = f"/api/reports/{assessment_id}"
    delivery_paths = (
        f"/api/export/{assessment_id}",
        f"/api/report/{assessment_id}/executive.csv",
        f"/api/report/{assessment_id}/executive.html",
    )

    internal = client.get(snapshot_path, headers=salus)
    assert internal.status_code == 200
    assert internal.headers["x-salus-report-status"] == "Draft"
    assert internal.headers["etag"] == f'"{digest}"'
    released_mission = internal.json()["assessment"]["mission"]

    for protected in (member, viewer):
        listing = client.get(list_path, headers=protected)
        assert listing.status_code == 200
        assert all(row["status"] == "Released" for row in listing.json())
        assert report_id not in {int(row["id"]) for row in listing.json()}
        assert client.get(snapshot_path, headers=protected).status_code == 404
        for path in delivery_paths:
            assert client.get(path, headers=protected).status_code == 404

    for status, role, user in (
        ("Reviewed", "Lead Assessor", "isolated-report-reviewer"),
        ("Approved", "System Administrator", "isolated-report-approver"),
        ("Released", "Assessment Director", "isolated-report-release-authority"),
    ):
        changed = client.post(
            f"/api/reports/versions/{report_id}/transition",
            headers=headers(tenant_id, role, user),
            json={"status": status, "reason": f"Isolated {status.lower()} acceptance"},
        )
        assert changed.status_code == 200, changed.text
        assert changed.json()["status"] == status

    for protected in (member, viewer):
        listing = client.get(list_path, headers=protected)
        assert listing.status_code == 200
        visible = [row for row in listing.json() if int(row["id"]) == report_id]
        assert len(visible) == 1 and visible[0]["status"] == "Released"
        delivered = client.get(snapshot_path, headers=protected)
        assert delivered.status_code == 200, delivered.text
        assert delivered.headers["x-salus-report-status"] == "Released"
        assert delivered.headers["etag"] == f'"{digest}"'
        assert "industry_defaults_snapshot_json" not in delivered.json()["assessment"]
        assert "industry_profile_applied_by" not in delivered.json()["assessment"]
        for path in delivery_paths:
            response = client.get(path, headers=protected)
            assert response.status_code == 200, (path, response.text)
            assert response.headers["x-salus-report-status"] == "Released"
            assert response.headers["etag"] == f'"{digest}"'

    assert client.get(snapshot_path, headers=other).status_code == 404

    conn = core.db()
    try:
        conn.execute(
            "UPDATE assessments SET mission=? WHERE id=?",
            ("Isolated unreleased change marker", assessment_id),
        )
        conn.commit()
    finally:
        conn.close()
    member_export = client.get(delivery_paths[0], headers=member)
    assert member_export.status_code == 200
    assert member_export.json()["assessment"]["mission"] == released_mission
    internal_preview = client.get(delivery_paths[0], headers=salus)
    assert internal_preview.status_code == 200
    assert internal_preview.json()["assessment"]["mission"] == "Isolated unreleased change marker"

    conn = core.db()
    try:
        stored = conn.execute(
            "SELECT snapshot_json FROM report_versions WHERE id=?", (report_id,)
        ).fetchone()["snapshot_json"]
        conn.execute(
            "UPDATE report_versions SET snapshot_json=? WHERE id=?",
            (stored + " ", report_id),
        )
        conn.commit()
    finally:
        conn.close()
    assert client.get(snapshot_path, headers=member).status_code == 409

    conn = core.db()
    try:
        conn.execute(
            "UPDATE report_versions SET snapshot_json=? WHERE id=?", (stored, report_id)
        )
        conn.execute(
            "UPDATE assessments SET mission=? WHERE id=?",
            (original_mission, assessment_id),
        )
        conn.commit()
    finally:
        conn.close()

    final = client.get(snapshot_path, headers=member)
    assert final.status_code == 200
    assert final.headers["etag"] == f'"{digest}"'
    print(
        json.dumps(
            {
                "acceptance": "LIVE_REPORTING_ACCEPTED",
                "candidate_release": "v3.111",
                "runtime_application_version": core.APP_VERSION,
                "fictional_environment_count": len(fixture_tenants),
                "protected_member_roles_verified": 2,
                "fictional_records_only": True,
                "delivery_formats_verified": 3,
                "draft_hidden": True,
                "cross_member_denied": True,
                "released_snapshot_immutable": True,
                "integrity_failure_denied": True,
                "human_release_authority_simulated_for_isolated_acceptance_only": True,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
