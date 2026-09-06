#!/usr/bin/env python3
"""Exercise governed tenant restore and rollback in an ephemeral clean room."""

import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "recovery.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "evidence"))
os.environ.setdefault("SALUS_STORAGE_BACKEND", "local")
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
os.environ["SALUS_ALLOW_RESTORE"] = "1"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app
from portable_backup import collect_tenant_records


def post(client, path, headers, payload=None, status=200):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == status, (path, response.status_code, response.text)
    return response.json() if response.content else None


def package_records(filename):
    path = Path(app.BACKUPS_DIR) / filename
    with zipfile.ZipFile(path, "r") as archive:
        package = json.loads(archive.read("records.json").decode("utf-8"))
    assert package["format"] == "salus-thira-records-v1"
    assert package["tenant_id"] == 1
    return package["tables"]


def assert_restored_snapshot(expected):
    conn = app.db()
    actual = collect_tenant_records(conn, 1)
    conn.close()
    for table, rows in expected.items():
        if table in {"audit_log", "security_events"}:
            continue
        assert actual.get(table) == rows, table


def main():
    client = TestClient(app.app)
    operator = {
        "X-Salus-Tenant": "1",
        "X-Salus-Role": "System Administrator",
        "X-Salus-User": "Recovery Operator",
        "X-Salus-Clearance": "Highly Sensitive",
    }
    reviewer = {
        **operator,
        "X-Salus-User": "Independent Recovery Reviewer",
    }

    # Establish an unrelated tenant boundary that both restore operations must preserve.
    conn = app.db()
    boundary_id = int(conn.execute("SELECT COALESCE(MAX(id),0)+100 AS id FROM tenants").fetchone()["id"])
    conn.execute(
        "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)",
        (boundary_id, "Recovery Boundary Tenant", f"recovery-boundary-{boundary_id}", "Active", app.now()),
    )
    conn.commit()
    boundary_before = dict(conn.execute("SELECT * FROM tenants WHERE id=?", (boundary_id,)).fetchone())
    conn.close()

    baseline = post(client, "/api/admin/backups", operator)
    verified = post(client, f"/api/admin/backups/{baseline['id']}/verify", operator)
    assert verified["ok"] is True
    validation = post(client, f"/api/admin/backups/{baseline['id']}/dr-validate", operator)
    assert validation["ok"] is True
    baseline_records = package_records(baseline["filename"])

    request = post(
        client,
        "/api/admin/restore-requests",
        operator,
        {
            "backup_id": baseline["id"],
            "scope": "Ephemeral tenant-one clean-room recovery rehearsal",
            "reason": "Validate restore isolation, integrity, authorization, and rollback.",
        },
    )
    # Separation of duties is mandatory.
    post(
        client,
        f"/api/admin/restore-requests/{request['id']}/decision",
        operator,
        {"decision": "Authorized", "reason": "Self-authorization must fail."},
        409,
    )
    decision = post(
        client,
        f"/api/admin/restore-requests/{request['id']}/decision",
        reviewer,
        {"decision": "Authorized", "reason": "Independent reviewer approved the ephemeral rehearsal."},
    )
    assert decision["status"] == "Authorized"

    marker = post(
        client,
        "/api/assessments",
        operator,
        {"name": "Pre-restore rollback marker", "organization": "Ephemeral recovery exercise"},
    )
    before_restore_ids = {
        row["id"] for row in client.get("/api/admin/backups", headers=operator).json()
    }
    restored = post(
        client,
        f"/api/admin/backups/{baseline['id']}/restore?restore_request_id={request['id']}",
        operator,
    )
    assert restored["ok"] is True
    conn = app.db()
    assert conn.execute("SELECT COUNT(*) AS c FROM assessments WHERE id=?", (marker["id"],)).fetchone()["c"] == 0
    assert dict(conn.execute("SELECT * FROM tenants WHERE id=?", (boundary_id,)).fetchone()) == boundary_before
    conn.close()
    assert_restored_snapshot(baseline_records)

    # The mandatory pre-restore safety backup is the rollback source.
    after_restore = client.get("/api/admin/backups", headers=operator).json()
    safety = next(row for row in after_restore if row["id"] not in before_restore_ids)
    assert safety["filename"] != baseline["filename"]
    assert safety["sha256"] != baseline["sha256"]
    safety_validation = post(client, f"/api/admin/backups/{safety['id']}/dr-validate", reviewer)
    assert safety_validation["ok"] is True
    safety_records = package_records(safety["filename"])
    rollback_request = post(
        client,
        "/api/admin/restore-requests",
        reviewer,
        {
            "backup_id": safety["id"],
            "scope": "Rollback to automatic pre-restore safety snapshot",
            "reason": "Prove bounded rollback to the exact pre-restore tenant state.",
        },
    )
    rollback_decision = post(
        client,
        f"/api/admin/restore-requests/{rollback_request['id']}/decision",
        operator,
        {"decision": "Authorized", "reason": "Independent rollback authorization granted."},
    )
    assert rollback_decision["status"] == "Authorized"
    rollback = post(
        client,
        f"/api/admin/backups/{safety['id']}/restore?restore_request_id={rollback_request['id']}",
        reviewer,
    )
    assert rollback["ok"] is True
    assert_restored_snapshot(safety_records)
    conn = app.db()
    assert conn.execute("SELECT COUNT(*) AS c FROM assessments WHERE id=?", (marker["id"],)).fetchone()["c"] == 1
    assert dict(conn.execute("SELECT * FROM tenants WHERE id=?", (boundary_id,)).fetchone()) == boundary_before
    executed = conn.execute(
        "SELECT * FROM restore_requests WHERE id=? AND status='Executed'",
        (rollback_request["id"],),
    ).fetchone()
    assert executed and executed["executed_by"] == "Independent Recovery Reviewer"
    assert conn.execute(
        "SELECT COUNT(*) AS c FROM audit_log WHERE action='RESTORE_EXECUTED'"
    ).fetchone()["c"] >= 1
    conn.close()

    # Admission closes after the exercise; an executed request cannot bypass it.
    app.ALLOW_RESTORE = False
    post(
        client,
        f"/api/admin/backups/{baseline['id']}/restore?restore_request_id={request['id']}",
        operator,
        status=403,
    )
    print("CLEAN_ROOM_RECOVERY_REHEARSAL_PASS", app.DB_BACKEND)


if __name__ == "__main__":
    main()
