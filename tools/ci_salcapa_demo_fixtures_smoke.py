#!/usr/bin/env python3
"""Deterministic acceptance checks for the Issue #124 fixture foundation."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile


root = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ["SALUS_ENV"] = "development"
os.environ["SALUS_SEED_DEMO"] = "0"
os.environ["SALUS_AUTH_MODE"] = "local"
backend = os.environ.get("SALUS_DB_BACKEND", "sqlite").strip().lower()
os.environ["SALUS_DB_BACKEND"] = backend
tmp = tempfile.TemporaryDirectory() if backend == "sqlite" else None
if tmp is not None:
    os.environ["SALUS_DB_PATH"] = str(pathlib.Path(tmp.name) / "fixtures.db")

import app as core  # noqa: E402
from salcapa_demo_fixtures import (  # noqa: E402
    DEMONSTRATION_ACKNOWLEDGEMENT,
    ENVIRONMENTS,
    FIXTURE_AUTHORITY,
    PERSONAS,
    RESEED_CONFIRMATION,
    register_demo_fixture_contract,
    seed_demo_environments,
)


register_demo_fixture_contract(core)
assert core.ROLE_PERMISSIONS["Protected Member Viewer"] == {"read"}
assert "Protected Member Viewer" in core.PROTECTED_MEMBER_ROLES


def run(operation: str = "seed", confirmation: str = ""):
    conn = core.db()
    try:
        return seed_demo_environments(
            conn,
            environment="development",
            authority=FIXTURE_AUTHORITY,
            acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
            operation=operation,
            confirmation=confirmation,
            now=lambda: "10-09-2026 11:30:00 UTC",
        )
    finally:
        conn.close()


conn = core.db()
conn.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)", ("Preserved Tenant", "preserved-tenant", "Active", core.now()))
conn.commit()
preserved_id = conn.execute("SELECT id FROM tenants WHERE slug='preserved-tenant'").fetchone()["id"]
conn.close()

first = run()
assert first["environment_count"] == 3
assert first["persona_count"] == 24
assert first["assessment_count"] == 3
assert first["assessment_access_count"] == 24
assert first["service_pillar_count"] == 12
assert first["journey_count"] == 3
assert first["record_state"] == "Draft"

second = run()
assert second["manifest_sha256"] == first["manifest_sha256"]

conn = core.db()
assert conn.execute("SELECT COUNT(*) c FROM tenants WHERE environment_kind='Fictional Demonstration'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM users WHERE identity_provider='demo-fixture'").fetchone()["c"] == 24
assert conn.execute("SELECT COUNT(*) c FROM users WHERE identity_provider='demo-fixture' AND password_hash<>''").fetchone()["c"] == 0
assert conn.execute("SELECT COUNT(*) c FROM users WHERE identity_provider='demo-fixture' AND email NOT LIKE '%@example.invalid'").fetchone()["c"] == 0
assert conn.execute("SELECT COUNT(DISTINCT external_subject) c FROM users WHERE identity_provider='demo-fixture'").fetchone()["c"] == 24
assert conn.execute("SELECT COUNT(*) c FROM assessments WHERE fixture_key<>'' AND status='Draft'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM assessment_access aa JOIN users u ON u.id=aa.user_id JOIN assessments a ON a.id=aa.assessment_id WHERE u.fixture_key<>'' AND a.fixture_key<>'' AND u.tenant_id=a.tenant_id").fetchone()["c"] == 24
assert conn.execute("SELECT COUNT(*) c FROM ops_service_pillars p JOIN tenants t ON t.id=p.tenant_id WHERE t.fixture_key<>''").fetchone()["c"] == 12
assert conn.execute("SELECT COUNT(*) c FROM intel_findings f JOIN tenants t ON t.id=f.tenant_id WHERE t.fixture_key<>'' AND f.status='Collected' AND f.validation_status='Unvalidated'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM threats h JOIN assessments a ON a.id=h.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>''").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM scenarios s JOIN assessments a ON a.id=s.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>''").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM capabilities c JOIN assessments a ON a.id=c.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>'' AND c.confidence='Low'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM evidence e JOIN assessments a ON a.id=e.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>'' AND e.verification_status='Pending'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM gaps g JOIN assessments a ON a.id=g.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>'' AND g.status='Open'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM improvements i JOIN assessments a ON a.id=i.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>'' AND i.status='Proposed' AND i.validation_status='Pending'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_coordination_threads c JOIN tenants t ON t.id=c.tenant_id WHERE t.fixture_key<>'' AND c.status='Open'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_coordination_messages m JOIN tenants t ON t.id=m.tenant_id WHERE t.fixture_key<>'' AND m.audience='Shared'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_coordination_messages m JOIN tenants t ON t.id=m.tenant_id WHERE t.fixture_key<>'' AND m.audience='Internal'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_decision_requests d JOIN tenants t ON t.id=d.tenant_id WHERE t.fixture_key<>'' AND d.status='Awaiting Decision' AND d.decision=''").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM ops_requests o JOIN tenants t ON t.id=o.tenant_id WHERE t.fixture_key<>'' AND o.status='Requested' AND o.authorized_by=''").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_events e JOIN tenants t ON t.id=e.tenant_id WHERE t.fixture_key<>'' AND e.event_type='Fixture Prepared'").fetchone()["c"] == 6
assert conn.execute("SELECT COUNT(*) c FROM decisions d JOIN assessments a ON a.id=d.assessment_id JOIN tenants t ON t.id=a.tenant_id WHERE t.fixture_key<>''").fetchone()["c"] == 0
assert conn.execute("SELECT COUNT(*) c FROM report_versions r JOIN tenants t ON t.id=r.tenant_id WHERE t.fixture_key<>'' AND r.status='Released'").fetchone()["c"] == 0
assert conn.execute("SELECT COUNT(*) c FROM tenants WHERE slug='preserved-tenant' AND id=?", (preserved_id,)).fetchone()["c"] == 1
assert conn.execute("SELECT COUNT(*) c FROM demo_fixture_runs").fetchone()["c"] == 2
conn.close()

reseeded = run("reseed", RESEED_CONFIRMATION)
assert reseeded["manifest_sha256"] == first["manifest_sha256"]
conn = core.db()
assert conn.execute("SELECT COUNT(*) c FROM tenants WHERE environment_kind='Fictional Demonstration'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM intel_findings f JOIN tenants t ON t.id=f.tenant_id WHERE t.fixture_key<>''").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM cop_decision_requests d JOIN tenants t ON t.id=d.tenant_id WHERE t.fixture_key<>'' AND d.status='Awaiting Decision'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM ops_requests o JOIN tenants t ON t.id=o.tenant_id WHERE t.fixture_key<>'' AND o.status='Requested'").fetchone()["c"] == 3
assert conn.execute("SELECT COUNT(*) c FROM tenants WHERE slug='preserved-tenant' AND id=?", (preserved_id,)).fetchone()["c"] == 1
assert conn.execute("SELECT COUNT(*) c FROM demo_fixture_runs").fetchone()["c"] == 3
conn.close()

for operation, confirmation in (("seed", ""), ("reseed", "wrong")):
    conn = core.db()
    try:
        try:
            seed_demo_environments(
                conn,
                environment="production" if operation == "seed" else "development",
                authority=FIXTURE_AUTHORITY,
                acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
                operation=operation,
                confirmation=confirmation,
                now=core.now,
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("A fail-closed fixture control did not reject the operation")
    finally:
        conn.close()

assert {environment.name for environment in ENVIRONMENTS} == {
    "Aster Ridge International Airport — fictional demonstration",
    "Cedar Vale Energy Systems — fictional demonstration",
    "Northstar Applied Technologies — fictional demonstration",
}
assert len(PERSONAS) == 8
print("SalCAPA fictional demonstration fixture smoke passed")
