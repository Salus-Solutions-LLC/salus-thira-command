#!/usr/bin/env python3
"""Acceptance checks for governed SalINTEL-to-SalTHIRA/SalOPS handoffs."""
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "handoffs.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from portable_backup import collect_tenant_records, replace_tenant_records, validate_records

app = salcapa_runtime.core


def main():
    client = TestClient(salcapa_runtime.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "Handoff Authority",
               "X-Salus-Clearance": "Highly Sensitive"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member User"}

    assessments = client.get("/api/assessments", headers=analyst)
    assert assessments.status_code == 200, assessments.text
    assessment_id = assessments.json()[0]["id"]

    created = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "personnel-assessment",
        "title": "SYNTHETIC Governed Handoff Assessment",
        "subject_reference": "SYNTHETIC-PERSON-HANDOFF-001",
        "purpose": "Lawful synthetic handoff acceptance.",
        "requested_tier": 1, "sensitivity": "Sensitive"})
    assert created.status_code == 200, created.text
    investigation_id = created.json()["id"]
    authorized = client.post(
        f"/api/salintel/investigations/{investigation_id}/authorize-tier",
        headers=analyst, json={
            "authorized_tier": 1,
            "scope_statement": "Bounded identity and protective relevance review.",
            "checklist_version": "personnel-assessment-1.0",
            "effort_bounds": {"maximum_human_hours": 2, "chat_cost_allowance_usd": 4},
            "source_categories": ["lawful public sources"],
            "exclusions": ["unrestricted dossiers"],
            "commercial_treatment": "Included",
            "commercial_reference": "SYNTHETIC-HANDOFF-T1",
            "investigative_lenses": ["Prevention", "Protection"],
            "reason": "Authorize bounded synthetic work."})
    assert authorized.status_code == 200, authorized.text
    assert client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Generate domain checklist."}).status_code == 200

    personnel = client.get(
        f"/api/salintel/personnel-assessments/{investigation_id}", headers=analyst)
    assert personnel.status_code == 200, personnel.text
    blockers = personnel.json()["completion_readiness"]["blockers"]
    assert any("shared Chat-led" in blocker for blocker in blockers), blockers

    premature = client.post(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=analyst, json={"target_component": "SalTHIRA",
        "assessment_id": assessment_id, "item_ids": [1],
        "summary": "Must remain blocked.", "rationale": "Not complete."})
    assert premature.status_code == 409, premature.text
    assert client.get(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=member).status_code == 403

    conn = app.db()
    ts = app.now()
    finding_detail = {"record_type": "personnel_finding", "schema_version": "1.0",
                      "category": "Protective-Intelligence Relevance",
                      "checklist_key": "PA1-OPEN",
                      "narrative": "A human-qualified synthetic protective implication.",
                      "protective_intelligence_relevance": True}
    cur = conn.execute(
        "INSERT INTO salintel_investigation_items(tenant_id,investigation_id,item_key,"
        "item_kind,epistemic_state,title,detail,source_reliability,"
        "information_confidence,source_material_id,member_visible,created_by,created_at,updated_at) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (1, investigation_id, "PAI-" + uuid.uuid4().hex, "Finding",
         "Analyst Judgment", "SYNTHETIC qualified protective implication",
         json.dumps(finding_detail, sort_keys=True, separators=(",", ":")),
         "Reliable", "Moderate", None, 0, "Handoff Authority", ts, ts),
    )
    finding_id = int(cur.lastrowid)
    conn.execute(
        "UPDATE salintel_investigations SET status='Tier Complete',completed_tier=1,"
        "qualification_status='Qualified',reviewed_by='Handoff Authority',reviewed_at=?,"
        "completion_statement='Synthetic bounded tier complete.',"
        "residual_unknowns='Synthetic known unknowns preserved.',updated_at=? WHERE id=?",
        (ts, ts, investigation_id),
    )
    conn.commit(); conn.close()

    ready = client.get(
        f"/api/salintel/investigations/{investigation_id}/handoffs", headers=analyst)
    assert ready.status_code == 200, ready.text
    assert ready.json()["readiness"]["ready"] is True
    assert {"SalTHIRA", "SalOPS"} <= set(ready.json()["readiness"]["allowed_targets"])
    assert finding_id in {item["id"] for item in ready.json()["readiness"]["eligible_items"]}

    forged = client.post(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=analyst, json={"target_component": "SalOPS",
        "assessment_id": assessment_id, "item_ids": [finding_id],
        "summary": "Synthetic operational relevance.",
        "rationale": "Authorized internal routing.",
        "status": "Authorized", "priority": "Critical",
        "member_disclosure_authorized": True})
    assert forged.status_code == 422, forged.text

    thira = client.post(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=analyst, json={"target_component": "SalTHIRA",
        "assessment_id": assessment_id, "item_ids": [finding_id],
        "summary": "Evaluate the qualified personnel implication in SalTHIRA.",
        "rationale": "A completed and human-qualified output may affect risk."})
    assert thira.status_code == 200, thira.text
    assert thira.json()["target_status"] == "Open"
    assert thira.json()["member_disclosure_authorized"] is False
    assert thira.json()["tier_change_authorized"] is False

    ops = client.post(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=analyst, json={"target_component": "SalOPS",
        "assessment_id": assessment_id, "item_ids": [finding_id],
        "summary": "Consider a bounded protective follow-up request.",
        "rationale": "Operational review is warranted without authorizing execution."})
    assert ops.status_code == 200, ops.text
    assert ops.json()["target_status"] == "Requested"
    assert ops.json()["operational_execution_authorized"] is False
    assert ops.json()["commercial_change_authorized"] is False
    assert client.post(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=analyst, json={"target_component": "SalOPS",
        "assessment_id": assessment_id, "item_ids": [finding_id],
        "summary": "Duplicate.", "rationale": "Must fail."}).status_code == 409

    conn = app.db()
    trigger = conn.execute(
        "SELECT * FROM reassessment_triggers WHERE id=?",
        (thira.json()["target_record_id"],),
    ).fetchone()
    assert trigger["source"] == "SalINTEL" and trigger["status"] == "Open"
    assert trigger["severity"] == "Moderate"
    request = conn.execute(
        "SELECT * FROM ops_requests WHERE id=? AND tenant_id=1",
        (ops.json()["target_record_id"],),
    ).fetchone()
    assert request["status"] == "Requested" and request["priority"] == "Routine"
    assert request["authorized_by"] == ""
    handoff_rows = list(conn.execute(
        "SELECT * FROM salintel_investigation_items WHERE investigation_id=? "
        "AND item_key LIKE 'SIHO-%' ORDER BY id", (investigation_id,)))
    assert len(handoff_rows) == 2 and all(int(row["member_visible"]) == 0 for row in handoff_rows)

    records = collect_tenant_records(conn, 1)
    assert not validate_records(records, 1)
    before = len([row for row in records["salintel_investigation_items"]
                  if str(row.get("item_key", "")).startswith("SIHO-")])
    replace_tenant_records(conn, 1, records)
    conn.commit()
    after = conn.execute(
        "SELECT COUNT(*) c FROM salintel_investigation_items WHERE tenant_id=1 "
        "AND item_key LIKE 'SIHO-%'").fetchone()["c"]
    assert before == after == 2
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) "
                 "VALUES(2,'Other Tenant','other-handoff','Active',?) "
                 "ON CONFLICT(id) DO NOTHING", (app.now(),))
    conn.commit(); conn.close()

    other = {**analyst, "X-Salus-Tenant": "2", "X-Salus-User": "Other Analyst"}
    assert client.get(
        f"/api/salintel/investigations/{investigation_id}/handoffs",
        headers=other).status_code == 403
    events = client.get(
        f"/api/salintel/investigations/{investigation_id}", headers=analyst).json()["events"]
    versions = [event["version_no"] for event in events]
    assert versions == list(range(1, len(versions) + 1))
    assert sum(event["event_type"] == "SALINTEL_HANDOFF_AUTHORIZED"
               for event in events) == 2
    print("SALCAPA_SALINTEL_HANDOFFS_PASS", app.DB_BACKEND)


if __name__ == "__main__":
    main()
