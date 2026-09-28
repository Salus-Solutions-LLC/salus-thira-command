"""Bounded SAL-D055 register smoke: lineage, tenant boundary, and Member choice."""
import sqlite3
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from salcapa_analytical_actions import register_analytical_actions


with tempfile.TemporaryDirectory() as temp:
    path = Path(temp) / "actions.db"

    def db():
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        return conn

    conn = db()
    conn.execute("CREATE TABLE assessments(id INTEGER PRIMARY KEY,tenant_id INTEGER)")
    conn.executemany("INSERT INTO assessments VALUES(?,?)", [(11, 1), (22, 2)])
    conn.commit()
    conn.close()

    def tenant(request):
        return int(request.headers.get("X-Test-Tenant", "1"))

    def actor(request):
        return request.headers.get("X-Test-Role", "Analyst")

    def require(request, permission):
        role = actor(request)
        if permission == "write" and role not in {"Analyst"}:
            raise HTTPException(403, "Write denied")
        if permission == "decide" and role != "Client Executive":
            raise HTTPException(403, "Decision denied")

    def salus(request, component):
        if actor(request) != "Analyst":
            raise HTTPException(403, "Salus-only")

    def member(request, action):
        require(request, "decide")

    def assessment(request, assessment_id):
        conn = db()
        try:
            row = conn.execute("SELECT * FROM assessments WHERE id=? AND tenant_id=?",
                               (assessment_id, tenant(request))).fetchone()
            if row is None:
                raise HTTPException(404, "Assessment not found")
            return dict(row)
        finally:
            conn.close()

    app = FastAPI()
    register_analytical_actions(app, {
        "db": db, "now": lambda: "2026-09-28T15:00:00Z", "tenant_id": tenant,
        "actor": actor, "require": require,
        "require_salus_component_authority": salus,
        "require_protected_member_authority": member,
        "assessment_row_for_request": assessment,
        "audit": lambda *args: None,
    })
    client = TestClient(app)
    payload = {
        "assessment_id": 11, "action_key": "G1-H1", "level": 1,
        "product": "SalTHIRA", "report_reference": "TLR-SALTHIRA-L1",
        "source_references": ["I1", "H1"],
        "working_assumption": "A listed exit may be unavailable during a flood.",
        "alternative": "A safe alternate exit may remain usable.",
        "recommendation_narrative": "Review road closure authority and test one safe alternate responder access path.",
        "checklist": [{"task": "Name the closure decision owner", "owner_role": "HOA Board",
                       "decision_window": "Before the next exercise",
                       "dependency_or_stop": "Do not open a damaged crossing",
                       "completion_proof": "Approved route-status record"}],
        "next_review": "After a qualified crossing inspection",
    }
    created = client.post("/api/salcapa/analytical-actions", json=payload)
    assert created.status_code == 200, created.text
    record = created.json()
    assert record["state"] == "Suggested"
    assert record["operational_authorization"] == "Not recorded by this register"
    action_id = record["id"]
    assert client.post("/api/salcapa/analytical-actions", json=payload).status_code == 409
    assert len(client.get("/api/salcapa/analytical-actions?assessment_id=11").json()) == 1
    assert client.get(f"/api/salcapa/analytical-actions/{action_id}",
                      headers={"X-Test-Tenant": "2"}).status_code == 404
    assert client.post(f"/api/salcapa/analytical-actions/{action_id}/member-decision",
                       json={"decision": "Member-selected", "decision_reference": "Board-2026-9",
                             "reason": "Request separate scoping"}).status_code == 403
    chosen = client.post(f"/api/salcapa/analytical-actions/{action_id}/member-decision",
                         headers={"X-Test-Role": "Client Executive"},
                         json={"decision": "Member-selected", "decision_reference": "Board-2026-9",
                               "reason": "Request separate scoping"})
    assert chosen.status_code == 200, chosen.text
    assert chosen.json()["state"] == "Member-selected"
    assert client.post(f"/api/salcapa/analytical-actions/{action_id}/revisions",
                       json={k: v for k, v in payload.items()
                             if k not in {"assessment_id", "action_key", "level", "product"}}).status_code == 409
    assert len(client.get(f"/api/salcapa/analytical-actions/{action_id}").json()["events"]) == 2

print("SAL-D055 analytical action register smoke passed")
