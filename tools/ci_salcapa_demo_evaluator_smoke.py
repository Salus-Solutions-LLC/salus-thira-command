#!/usr/bin/env python3
"""Acceptance checks for the governed Issue #124 evaluator view."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_ENV": "development",
    "SALUS_SEED_DEMO": "0",
    "SALUS_AUTH_MODE": "prototype",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "demo-evaluator.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_demo_evaluator import EXPECTED_KEYS, register_demo_evaluator  # noqa: E402
from salcapa_demo_fixtures import (  # noqa: E402
    DEMONSTRATION_ACKNOWLEDGEMENT,
    FIXTURE_AUTHORITY,
    register_demo_fixture_contract,
    seed_demo_environments,
)


register_demo_fixture_contract(core)
register_demo_evaluator(core)
conn = core.db()
try:
    seed_demo_environments(
        conn,
        environment="development",
        authority=FIXTURE_AUTHORITY,
        acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
        operation="seed",
        confirmation="",
        now=lambda: "12-09-2026 02:15:00 UTC",
    )
    conn.execute(
        """INSERT INTO tenants(name,slug,status,created_at,environment_kind,display_label,fixture_key,fixture_version)
           VALUES(?,?,?,?,?,?,?,?)""",
        (
            "Unapproved Fictional Environment",
            "unapproved-fictional",
            "Active",
            core.now(),
            "Fictional Demonstration",
            DEMONSTRATION_ACKNOWLEDGEMENT,
            "unapproved-fixture",
            "unapproved",
        ),
    )
    conn.commit()
finally:
    conn.close()

ADMIN = {"X-Salus-Tenant": "1", "X-Salus-Role": "System Administrator", "X-Salus-User": "Salus Evaluator"}
DIRECTOR = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Salus Facilitator"}
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
AUDITOR = {"X-Salus-Tenant": "1", "X-Salus-Role": "Auditor", "X-Salus-User": "Read-only Auditor"}

with TestClient(core.app) as client:
    for headers in (ADMIN, DIRECTOR):
        response = client.get("/api/demonstration-environments", headers=headers)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["environment_count"] == 3
        assert body["label"] == DEMONSTRATION_ACKNOWLEDGEMENT
        assert body["access_mode"] == "Read-only Salus evaluation"
        assert tuple(item["key"] for item in body["environments"]) == EXPECTED_KEYS
        assert {item["name"] for item in body["environments"]} == {
            "Aster Ridge International Airport — fictional demonstration",
            "Cedar Vale Energy Systems — fictional demonstration",
            "Northstar Applied Technologies — fictional demonstration",
        }
        assert all(item["assessments"] for item in body["environments"])
        assert all(item["intelligence"] for item in body["environments"])
        assert all(item["coordination"] for item in body["environments"])
        assert all(item["decisions"] for item in body["environments"])
        assert all(item["operations"] for item in body["environments"])
        assert all(item["counts"]["threats_and_hazards"] == 1 for item in body["environments"])
        assert all("tenant_id" not in item for item in body["environments"])
        assert "Unapproved Fictional Environment" not in str(body)
        assert "password" not in str(body).lower()

    assert client.get("/api/demonstration-environments", headers=MEMBER).status_code == 403
    assert client.get("/api/demonstration-environments", headers=AUDITOR).status_code == 403
    assert client.post("/api/demonstration-environments", headers=ADMIN).status_code == 405
    tenant_one = client.get("/api/assessments", headers=ADMIN)
    assert tenant_one.status_code == 200
    assert not any(item.get("fixture_key") in EXPECTED_KEYS for item in tenant_one.json())

index = (ROOT / "static/index.html").read_text(encoding="utf-8")
app_js = (ROOT / "static/app.js").read_text(encoding="utf-8")
evaluator_js = (ROOT / "static/demo-environments.js").read_text(encoding="utf-8")
assert 'data-view="demo_environments"' in index
assert 'data-salus-only="true"' in index
assert '/static/demo-environments.js' in index
assert "SalusDemoEnvironments" in app_js
for name in ("Aster Ridge", "Cedar Vale", "Northstar"):
    assert name not in evaluator_js, "The UI must render only server-authorized fixture records"
for forbidden in ("X-Salus-Tenant", "localStorage", "impersonat", "method:'POST'", 'method:"POST"'):
    assert forbidden not in evaluator_js
module = (ROOT / "salcapa_demo_evaluator.py").read_text(encoding="utf-8").lower()
for forbidden_sql in ("insert into", "update tenants", "delete from"):
    assert forbidden_sql not in module
print("SALCAPA_DEMO_EVALUATOR_SMOKE_PASS", core.DB_BACKEND)

