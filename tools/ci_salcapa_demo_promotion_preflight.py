#!/usr/bin/env python3
"""Fail-closed role, tenant, recovery, and promotion preflight for Issue #124."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile

from fastapi.testclient import TestClient


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["SALUS_ENV"] = "development"
os.environ["SALUS_SEED_DEMO"] = "0"
os.environ["SALUS_AUTH_MODE"] = "local"
backend = os.environ.get("SALUS_DB_BACKEND", "sqlite").strip().lower()
os.environ["SALUS_DB_BACKEND"] = backend
temporary = tempfile.TemporaryDirectory() if backend == "sqlite" else None
if temporary is not None:
    os.environ["SALUS_DB_PATH"] = str(pathlib.Path(temporary.name) / "promotion-preflight.db")

import app as core  # noqa: E402
from portable_backup import collect_tenant_records, validate_records  # noqa: E402
from salcapa_demo_evaluator import register_demo_evaluator  # noqa: E402
from salcapa_demo_fixtures import (  # noqa: E402
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


def front_matter(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return {
        key.strip(): value.strip()
        for line in raw.strip().splitlines()
        for key, _, value in [line.partition(":")]
    }


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
        now=lambda: "10-09-2026 13:00:00 UTC",
    )
finally:
    conn.close()

# Reapplying additive schema and fixture operations must preserve record identity.
conn = core.db()
count_queries = {
    "tenants": "SELECT COUNT(*) c FROM tenants",
    "users": "SELECT COUNT(*) c FROM users",
    "assessments": "SELECT COUNT(*) c FROM assessments",
    "intel_findings": "SELECT COUNT(*) c FROM intel_findings",
    "threats": "SELECT COUNT(*) c FROM threats",
    "scenarios": "SELECT COUNT(*) c FROM scenarios",
    "capabilities": "SELECT COUNT(*) c FROM capabilities",
    "evidence": "SELECT COUNT(*) c FROM evidence",
    "gaps": "SELECT COUNT(*) c FROM gaps",
    "improvements": "SELECT COUNT(*) c FROM improvements",
    "cop_coordination_threads": "SELECT COUNT(*) c FROM cop_coordination_threads",
    "cop_coordination_messages": "SELECT COUNT(*) c FROM cop_coordination_messages",
    "cop_decision_requests": "SELECT COUNT(*) c FROM cop_decision_requests",
    "ops_requests": "SELECT COUNT(*) c FROM ops_requests",
}
before = {table: conn.execute(query).fetchone()["c"] for table, query in count_queries.items()}
conn.close()
register_demo_fixture_contract(core)
conn = core.db()
try:
    seed_demo_environments(
        conn,
        environment="development",
        authority=FIXTURE_AUTHORITY,
        acknowledgement=DEMONSTRATION_ACKNOWLEDGEMENT,
        operation="seed",
        now=lambda: "10-09-2026 13:01:00 UTC",
    )
finally:
    conn.close()
conn = core.db()
after = {table: conn.execute(query).fetchone()["c"] for table, query in count_queries.items()}
assert after == before
assert conn.execute(
    "SELECT COUNT(*) c FROM schema_migrations WHERE version='3.110-demo-fixture-role-preflight-v3'"
).fetchone()["c"] == 1

tenants = [
    dict(row)
    for row in conn.execute(
        "SELECT * FROM tenants WHERE environment_kind='Fictional Demonstration' ORDER BY id"
    )
]
assert len(tenants) == 3
assert conn.execute(
    "SELECT COUNT(*) c FROM auth_sessions s JOIN users u ON u.id=s.user_id "
    "WHERE u.identity_provider='demo-fixture'"
).fetchone()["c"] == 0
assert conn.execute(
    "SELECT COUNT(*) c FROM assessment_access aa "
    "JOIN users u ON u.id=aa.user_id JOIN assessments a ON a.id=aa.assessment_id "
    "WHERE u.fixture_key<>'' AND a.fixture_key<>'' AND u.tenant_id<>a.tenant_id"
).fetchone()["c"] == 0
assert conn.execute(
    "SELECT COUNT(*) c FROM cop_coordination_messages WHERE audience='Internal'"
).fetchone()["c"] == 3

# Portable packages must remain tenant-scoped and internally referentially valid.
for tenant in tenants:
    records = collect_tenant_records(conn, tenant["id"])
    errors = validate_records(records, tenant["id"])
    assert not errors, errors
conn.close()

client = TestClient(core.app)

# The normal read-only evaluator route must expose exactly the governed fixture
# set without changing tenant identity, impersonating a persona, or creating authority.
evaluator_headers = headers(
    int(tenants[0]["id"]),
    "System Administrator",
    "Salus Evaluator",
)
evaluator_response = client.get(
    "/api/salcapa/demonstration-environments",
    headers=evaluator_headers,
)
assert evaluator_response.status_code == 200, evaluator_response.text
evaluator_body = evaluator_response.json()
assert evaluator_body["environment_count"] == 3
assert evaluator_body["access_mode"] == "Read-only Salus evaluation"
assert {item["key"] for item in evaluator_body["environments"]} == {
    "aster-ridge-airport",
    "cedar-vale-energy",
    "northstar-applied-technologies",
}
assert all(item["assessments"] for item in evaluator_body["environments"])
assert all(item["intelligence"] for item in evaluator_body["environments"])
assert all(item["coordination"] for item in evaluator_body["environments"])
assert all(item["operations"] for item in evaluator_body["environments"])
assert all("tenant_id" not in item for item in evaluator_body["environments"])
assert client.get(
    "/api/salcapa/demonstration-environments",
    headers=headers(int(tenants[0]["id"]), "Contributor", "Protected Member Contributor"),
).status_code == 403

decision_ids: list[tuple[int, int]] = []
internal_only_fields = {
    "details", "source", "source_locator", "created_by", "assigned_by",
    "withdrawn_by", "withdrawal_reason", "authorized_by", "authorization_reason",
}

for tenant in tenants:
    tenant_id = int(tenant["id"])
    analyst = headers(
        tenant_id,
        "SME Assessor",
        f"demo.{tenant['fixture_key']}.salus-intelligence-analyst",
    )
    viewer = headers(
        tenant_id,
        "Protected Member Viewer",
        f"demo.{tenant['fixture_key']}.member-read-only",
    )
    contributor = headers(
        tenant_id,
        "Contributor",
        f"demo.{tenant['fixture_key']}.member-operations-lead",
    )

    access = client.get("/api/system/access", headers=viewer)
    assert access.status_code == 200 and access.json()["permissions"] == ["read"]
    member_workspace = client.get("/api/salcapa/workspace", headers=viewer).json()
    assert member_workspace["experience"] == "Protected Member"
    assert not any(member_workspace["component_authority"].values())
    assert "SalINTEL" not in member_workspace["workspaces"]
    analyst_workspace = client.get("/api/salcapa/workspace", headers=analyst).json()
    assert analyst_workspace["experience"] == "Salus Personnel"
    assert {"SalINTEL", "SalTHIRA", "SalOPS"}.issubset(analyst_workspace["workspaces"])

    internal_findings = client.get("/api/salintel/findings", headers=analyst)
    member_findings = client.get("/api/salintel/findings", headers=viewer)
    assert internal_findings.status_code == 200 and len(internal_findings.json()) == 1
    assert internal_findings.json()[0]["status"] == "Collected"
    assert member_findings.status_code == 200 and member_findings.json() == []

    member_cop = client.get("/api/salcapa/common-operating-picture", headers=viewer)
    internal_cop = client.get("/api/salcapa/common-operating-picture", headers=analyst)
    assert member_cop.status_code == internal_cop.status_code == 200
    member_body, internal_body = member_cop.json(), internal_cop.json()
    assert member_body["metrics"]["pending_member_decisions"] == 1
    assert member_body["metrics"]["active_operations"] == 1
    assert len(member_body["coordinate"]["threads"]) == 1
    assert len(member_body["coordinate"]["threads"][0]["messages"]) == 1
    assert len(internal_body["coordinate"]["threads"][0]["messages"]) == 2
    assert not (internal_only_fields & set(member_body["see"]["operations"][0]))
    assert not (internal_only_fields & set(member_body["act"]["decision_requests"][0]))
    decision_ids.append((tenant_id, member_body["act"]["decision_requests"][0]["id"]))

    thread_id = member_body["coordinate"]["threads"][0]["id"]
    denied = client.post(
        f"/api/salcapa/coordination/threads/{thread_id}/messages",
        headers=viewer,
        json={"audience": "Shared", "body": "Read-only users cannot add messages."},
    )
    assert denied.status_code == 403
    hidden = client.post(
        f"/api/salcapa/coordination/threads/{thread_id}/messages",
        headers=contributor,
        json={"audience": "Internal", "body": "Protected Members cannot create internal notes."},
    )
    assert hidden.status_code == 403, hidden.text

# A Protected Member authority from another tenant cannot decide this tenant's request.
first_tenant, first_decision = decision_ids[0]
other_tenant = decision_ids[1][0]
cross_tenant = client.post(
    f"/api/salcapa/decision-requests/{first_decision}/decide",
    headers=headers(other_tenant, "Client Executive", "fictional-other-member-executive"),
    json={
        "decision": "Defer",
        "rationale": "Cross-tenant denial test.",
        "conditions": "",
        "authorized_amount": "0",
    },
)
assert cross_tenant.status_code == 403 and first_tenant != other_tenant

# Repository evidence records the exact v3.113 promotion candidate while the
# accepted v3.112 demonstration remains the fail-closed baseline until live acceptance.
deployment = front_matter(ROOT / "docs" / "demo-deployment-continuity.md")
assert deployment["current_stable_release"] == "v3.113"
assert deployment["current_stable_commit"] == "9d9873203fffd8c8ae477123ea94eb35b27c2acd"
assert deployment["promotion_candidate"] == "v3.113"
assert deployment["promotion_candidate_image_commit"] == "9d9873203fffd8c8ae477123ea94eb35b27c2acd"
assert deployment["promotion_candidate_image_digest"] == "sha256:84fe4ca875ec1d8478aa617fcd873adcf62c5eba78134ea4575de8471bfd9eb8"
if deployment["promotion_readiness"] == "accepted":
    assert deployment["deployed_release"] == "v3.113"
    assert deployment["deployed_commit"] == "9d9873203fffd8c8ae477123ea94eb35b27c2acd"
    assert deployment["fictional_member_seed_state"] == "verified"
    assert deployment["critical_journey_acceptance"] == "verified"
    assert deployment["genuine_blocker"] == "none"
else:
    assert deployment["deployed_release"] in {"v3.112", "v3.113"}
    if deployment["deployed_release"] == "v3.112":
        assert deployment["deployed_commit"] == "1d1759375d37b7de884331c06833de8c727ac5af"
    else:
        assert deployment["deployed_commit"] == "9d9873203fffd8c8ae477123ea94eb35b27c2acd"
    assert deployment["promotion_readiness"] in {"preflight_ready", "deployed_awaiting_live_acceptance"}
    if deployment["deployed_release"] == "v3.113":
        assert deployment["promotion_readiness"] == "deployed_awaiting_live_acceptance"
        assert deployment["promotion_candidate_image_acceptance"] == "immutable_image_deployed_awaiting_live_acceptance"
    assert deployment["critical_journey_acceptance"] == "not_verified"
    assert deployment["genuine_blocker"] != "none"

print("SalCAPA demonstration role, tenant, recovery, and governed-state preflight passed.")
