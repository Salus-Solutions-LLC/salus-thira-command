#!/usr/bin/env python3
"""Rehearse v3.36-to-current migration, reporting, recovery, and rollback.

The accepted source is checked out separately at its exact frozen commit.  This
test never connects to Azure and never changes the accepted demonstration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ACCEPTED_COMMIT = "63d513605f908d3308bb5dd1bbdbf1061878452b"
CANDIDATE_COMMIT = "8bf4614ec79a27641c40dc1a21e1790746a08604"
ACCEPTED_BLOBS = {
    "app.py": "ff336aa87b387eb4f1f9f1bd55b93e923c74ab2c",
    "database.py": "531b3c417692d0d40ada03eda79f9ea114168517",
    "portable_backup.py": "0fdb13eb298a0248c2ae8dac4e766e01a2dd60f4",
    "requirements.txt": "2fed82737c37b1b3a0cd9a85c867b314932beb24",
}

BASELINE_QUERIES = {
    "tenants": (
        "SELECT id,name,slug,status,created_at FROM tenants WHERE id=? ORDER BY id"
    ),
    "assessments": (
        "SELECT id,tenant_id,name,organization,status,classification,version,created_at,updated_at "
        "FROM assessments WHERE tenant_id=? ORDER BY id"
    ),
    "threats": (
        "SELECT id,assessment_id,name,category,description,status,created_at,updated_at "
        "FROM threats WHERE assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?) ORDER BY id"
    ),
    "scenarios": (
        "SELECT id,assessment_id,threat_id,title,narrative,created_at,updated_at "
        "FROM scenarios WHERE assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?) ORDER BY id"
    ),
    "capabilities": (
        "SELECT id,assessment_id,scenario_id,name,mission_area,required_outcome,created_at,updated_at "
        "FROM capabilities WHERE assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?) ORDER BY id"
    ),
    "gaps": (
        "SELECT id,assessment_id,capability_id,gap_type,description,status,created_at,updated_at "
        "FROM gaps WHERE assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?) ORDER BY id"
    ),
    "improvements": (
        "SELECT id,assessment_id,gap_id,title,description,status,created_at,updated_at "
        "FROM improvements WHERE assessment_id IN (SELECT id FROM assessments WHERE tenant_id=?) ORDER BY id"
    ),
    "audit_log": (
        "SELECT id,ts,user_name,action,entity_type,entity_id,detail,tenant_id "
        "FROM audit_log WHERE tenant_id=? ORDER BY id"
    ),
    "schema_migrations": (
        "SELECT version FROM schema_migrations WHERE ? IS NOT NULL ORDER BY version"
    ),
    "ops_service_pillars": (
        "SELECT id,tenant_id,pillar_code,name,description,sort_order,status,created_by,created_at "
        "FROM ops_service_pillars WHERE tenant_id=? ORDER BY id"
    ),
}


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def git_blob_sha(path: Path) -> str:
    body = path.read_bytes()
    # SHA-1 is required by the Git blob identity format, not used as a security digest.
    return hashlib.sha1(
        f"blob {len(body)}\0".encode("ascii") + body,
        usedforsecurity=False,
    ).hexdigest()


def snapshot(conn: Any, tenant_id: int) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for table, query in BASELINE_QUERIES.items():
        rows = [dict(row) for row in conn.execute(query, (tenant_id,))]
        result[table] = {"count": len(rows), "sha256": digest(rows)}
    return result


def accepted_seed(manifest_path: Path, accepted_root: Path) -> None:
    sys.path.insert(0, str(accepted_root))
    os.chdir(accepted_root)
    import app as accepted  # noqa: E402

    assert accepted.APP_VERSION == "1.16.0"
    conn = accepted.db()
    try:
        tenant = dict(conn.execute("SELECT id,slug FROM tenants ORDER BY id LIMIT 1").fetchone())
        baseline = snapshot(conn, int(tenant["id"]))
        assert baseline["tenants"]["count"] == 1
        for table in ("assessments", "threats", "scenarios", "capabilities", "gaps", "improvements"):
            assert baseline[table]["count"] == 1
        assessment = dict(conn.execute("SELECT id,name FROM assessments ORDER BY id LIMIT 1").fetchone())
    finally:
        conn.close()
    manifest_path.write_text(
        json.dumps(
            {
                "accepted_commit": ACCEPTED_COMMIT,
                "accepted_application_version": accepted.APP_VERSION,
                "tenant": tenant,
                "assessment": assessment,
                "baseline": baseline,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def tenant_package_digest(collect_tenant_records: Any, conn: Any, tenant_id: int) -> str:
    return digest(collect_tenant_records(conn, tenant_id))


def current_migrate(manifest_path: Path) -> None:
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)
    import app as core  # noqa: E402
    from fastapi.testclient import TestClient  # noqa: E402
    from portable_backup import (  # noqa: E402
        collect_tenant_records,
        replace_tenant_records,
        validate_records,
    )
    from salcapa_demo_fixtures import (  # noqa: E402
        DEMONSTRATION_ACKNOWLEDGEMENT,
        FIXTURE_AUTHORITY,
        register_demo_fixture_contract,
        seed_demo_environments,
    )

    register_demo_fixture_contract(core)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    tenant_id = int(manifest["tenant"]["id"])
    assessment_id = int(manifest["assessment"]["id"])

    conn = core.db()
    try:
        migrated = snapshot(conn, tenant_id)
        for table, expected in manifest["baseline"].items():
            if table != "schema_migrations":
                assert migrated[table] == expected, table
        migration_count = conn.execute(
            "SELECT COUNT(*) c FROM schema_migrations"
        ).fetchone()["c"]
        assert migration_count > manifest["baseline"]["schema_migrations"]["count"]
        seed_demo_environments(
            conn,
            environment="development",
            authority=FIXTURE_AUTHORITY,
            acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
            operation="seed",
            now=lambda: "10-09-2026 19:00:00 UTC",
        )
        after_seed = snapshot(conn, tenant_id)
        for table, expected in manifest["baseline"].items():
            if table != "schema_migrations":
                assert after_seed[table] == expected, table
        fixture_tenants = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM tenants WHERE environment_kind='Fictional Demonstration' ORDER BY id"
            )
        ]
        assert len(fixture_tenants) == 3
    finally:
        conn.close()

    headers = {
        "X-Salus-Tenant": str(tenant_id),
        "X-Salus-Role": "SME Assessor",
        "X-Salus-User": "v336-migration-rehearsal",
    }
    member_headers = {
        "X-Salus-Tenant": str(tenant_id),
        "X-Salus-Role": "Client Executive",
        "X-Salus-User": "protected-member-report-authority",
    }
    viewer_headers = {
        "X-Salus-Tenant": str(tenant_id),
        "X-Salus-Role": "Protected Member Viewer",
        "X-Salus-User": "protected-member-report-viewer",
    }
    client = TestClient(core.app)
    report = client.post(f"/api/reports/{assessment_id}", headers=headers, json={})
    assert report.status_code == 200, report.text
    report_row = report.json()
    rendered = client.get(
        f"/api/reports/versions/{report_row['id']}/snapshot", headers=headers
    )
    assert rendered.status_code == 200
    assert rendered.headers["x-salus-report-status"] == "Draft"
    assert rendered.headers["etag"] == f'"{report_row["snapshot_sha256"]}"'

    # Draft and in-review reports remain Salus work product. Protected Member
    # delivery is bound to the immutable Released snapshot, including the
    # familiar JSON, CSV, and printable HTML routes.
    snapshot_path = f"/api/reports/versions/{report_row['id']}/snapshot"
    report_list_path = f"/api/reports/{assessment_id}"
    delivery_paths = (
        f"/api/export/{assessment_id}",
        f"/api/report/{assessment_id}/executive.csv",
        f"/api/report/{assessment_id}/executive.html",
    )
    for protected_headers in (member_headers, viewer_headers):
        assert client.get(report_list_path, headers=protected_headers).json() == []
        assert client.get(snapshot_path, headers=protected_headers).status_code == 404
        for path in delivery_paths:
            assert client.get(path, headers=protected_headers).status_code == 404

    transitions = (
        ("Reviewed", "Lead Assessor", "report-reviewer"),
        ("Approved", "System Administrator", "report-approver"),
        ("Released", "Assessment Director", "report-release-authority"),
    )
    released_row = None
    for status, authority_role, authority_user in transitions:
        authority_headers = {
            "X-Salus-Tenant": str(tenant_id),
            "X-Salus-Role": authority_role,
            "X-Salus-User": authority_user,
        }
        transition = client.post(
            f"/api/reports/versions/{report_row['id']}/transition",
            headers=authority_headers,
            json={"status": status, "reason": f"Governed {status.lower()} acceptance"},
        )
        assert transition.status_code == 200, transition.text
        released_row = transition.json()
    assert released_row and released_row["status"] == "Released"

    for protected_headers in (member_headers, viewer_headers):
        visible = client.get(report_list_path, headers=protected_headers)
        assert visible.status_code == 200, visible.text
        assert len(visible.json()) == 1 and visible.json()[0]["status"] == "Released"
        delivered = client.get(snapshot_path, headers=protected_headers)
        assert delivered.status_code == 200, delivered.text
        assert delivered.headers["x-salus-report-status"] == "Released"
        assert delivered.headers["etag"] == f'"{report_row["snapshot_sha256"]}"'
        assert "industry_defaults_snapshot_json" not in delivered.json()["assessment"]
        assert "industry_profile_applied_by" not in delivered.json()["assessment"]
        for path in delivery_paths:
            response = client.get(path, headers=protected_headers)
            assert response.status_code == 200, (path, response.text)
            assert response.headers["x-salus-report-status"] == "Released"
            assert response.headers["etag"] == f'"{report_row["snapshot_sha256"]}"'

    other_tenant_headers = {
        "X-Salus-Tenant": str(fixture_tenants[0]),
        "X-Salus-Role": "Client Executive",
        "X-Salus-User": "other-protected-member",
    }
    assert client.get(snapshot_path, headers=other_tenant_headers).status_code == 404

    released_mission = rendered.json()["assessment"]["mission"]
    conn = core.db()
    conn.execute(
        "UPDATE assessments SET mission=? WHERE id=?",
        ("Unreleased reporting-change marker", assessment_id),
    )
    conn.commit()
    conn.close()
    member_export = client.get(f"/api/export/{assessment_id}", headers=member_headers)
    assert member_export.status_code == 200, member_export.text
    assert member_export.json()["assessment"]["mission"] == released_mission
    internal_preview = client.get(f"/api/export/{assessment_id}", headers=headers)
    assert internal_preview.status_code == 200, internal_preview.text
    assert internal_preview.json()["assessment"]["mission"] == "Unreleased reporting-change marker"
    conn = core.db()
    conn.execute(
        "UPDATE assessments SET mission=? WHERE id=?", (released_mission, assessment_id)
    )
    conn.commit()
    conn.close()

    conn = core.db()
    try:
        baseline_records = collect_tenant_records(conn, tenant_id)
        assert not validate_records(baseline_records, tenant_id)
        fixture_before = {
            item: tenant_package_digest(collect_tenant_records, conn, item)
            for item in fixture_tenants
        }
        original_name = conn.execute(
            "SELECT name FROM assessments WHERE id=?", (assessment_id,)
        ).fetchone()["name"]
        conn.execute(
            "UPDATE assessments SET name=? WHERE id=?",
            ("Pre-restore rollback marker", assessment_id),
        )
        conn.commit()
        safety_records = collect_tenant_records(conn, tenant_id)

        replace_tenant_records(conn, tenant_id, baseline_records)
        restored_name = conn.execute(
            "SELECT name FROM assessments WHERE id=?", (assessment_id,)
        ).fetchone()["name"]
        assert restored_name == original_name
        assert conn.execute(
            "SELECT snapshot_sha256 FROM report_versions WHERE id=?", (report_row["id"],)
        ).fetchone()["snapshot_sha256"] == report_row["snapshot_sha256"]

        replace_tenant_records(conn, tenant_id, safety_records)
        rollback_name = conn.execute(
            "SELECT name FROM assessments WHERE id=?", (assessment_id,)
        ).fetchone()["name"]
        assert rollback_name == "Pre-restore rollback marker"
        fixture_after = {
            item: tenant_package_digest(collect_tenant_records, conn, item)
            for item in fixture_tenants
        }
        assert fixture_after == fixture_before
    finally:
        conn.close()

    print(
        "Accepted v3.36 migration, report integrity, tenant recovery, and rollback rehearsal passed; "
        "Azure was not contacted or changed."
    )


def run_parent() -> None:
    accepted_root_value = os.environ.get("SALCAPA_ACCEPTED_V336_ROOT", "").strip()
    assert accepted_root_value, "SALCAPA_ACCEPTED_V336_ROOT is required"
    accepted_root = Path(accepted_root_value).resolve()
    assert accepted_root != ROOT
    for relative, expected in ACCEPTED_BLOBS.items():
        path = accepted_root / relative
        assert path.is_file(), f"Accepted v3.36 source is missing {relative}"
        assert git_blob_sha(path) == expected, f"Accepted v3.36 source mismatch: {relative}"

    activation = json.loads(
        (ROOT / "deploy" / "azure" / "activations" / "application-dev.json").read_text(
            encoding="utf-8"
        )
    )
    assert activation["source_commit"] == CANDIDATE_COMMIT
    assert activation["source_release"] == "release/v3.111"
    assert activation["image_digest"].startswith(
        "salcapadevb48224acr.azurecr.io/salcapa@sha256:"
    )
    assert activation["rollback_commit"] == ACCEPTED_COMMIT
    assert activation["rollback_release"] == "release/v3.36"
    assert activation["rollback_image_digest"].startswith(
        "salcapadevb48224acr.azurecr.io/salcapa@sha256:"
    )

    backend = os.environ.get("SALUS_DB_BACKEND", "sqlite").strip().lower()
    environment = os.environ.copy()
    environment.update(
        {
            "SALUS_ENV": "development",
            "SALUS_AUTH_MODE": "local",
            "SALUS_COOKIE_SECURE": "0",
            "SALUS_ALLOW_RESTORE": "1",
            "SALUS_DB_BACKEND": backend,
        }
    )

    with tempfile.TemporaryDirectory() as temporary:
        temp = Path(temporary)
        manifest_path = temp / "accepted-v336-baseline.json"
        environment["SALUS_LOCAL_STORAGE_DIR"] = str(temp / "attachments")
        environment["SALUS_BACKUP_DIR"] = str(temp / "backups")
        if backend == "sqlite":
            environment["SALUS_DB_PATH"] = str(temp / "v336-migration.db")
        elif backend != "postgres":
            raise AssertionError(f"Unsupported database backend: {backend}")

        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "accepted-seed", str(manifest_path)],
            cwd=accepted_root,
            env={
                **environment,
                "SALCAPA_ACCEPTED_V336_ROOT": str(accepted_root),
                "SALUS_SEED_DEMO": "1",
            },
            check=True,
        )
        subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "current-migrate", str(manifest_path)],
            cwd=ROOT,
            env={**environment, "SALUS_SEED_DEMO": "0"},
            check=True,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", nargs="?", choices=("accepted-seed", "current-migrate"))
    parser.add_argument("manifest", nargs="?")
    args = parser.parse_args()
    if args.mode == "accepted-seed":
        accepted_seed(Path(args.manifest), Path(os.environ["SALCAPA_ACCEPTED_V336_ROOT"]))
    elif args.mode == "current-migrate":
        current_migrate(Path(args.manifest))
    else:
        run_parent()


if __name__ == "__main__":
    main()
