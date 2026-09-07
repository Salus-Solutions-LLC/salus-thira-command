#!/usr/bin/env python3
"""Acceptance checks for the governed Personnel Assessment foundation."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "personnel.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from portable_backup import collect_tenant_records, replace_tenant_records

app = salcapa_runtime.core


def main():
    client = TestClient(salcapa_runtime.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "Personnel Analyst",
               "X-Salus-Clearance": "Highly Sensitive"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member User"}

    checklist = client.get("/api/salintel/personnel-assessment/checklist",
                           headers=analyst)
    assert checklist.status_code == 200
    assert checklist.json()["version"] == "personnel-assessment-1.0"
    assert {row["tier_required"] for row in checklist.json()["tiers"]} == {1, 2, 3}
    assert client.get("/api/salintel/personnel-assessment/checklist",
                      headers=member).status_code == 403

    created = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "personnel-assessment",
        "title": "SYNTHETIC Personnel Assessment",
        "subject_reference": "SYNTHETIC-PERSON-001",
        "purpose": "Lawful synthetic suitability and protective-intelligence assessment.",
        "requested_tier": 1, "sensitivity": "Sensitive"})
    assert created.status_code == 200, created.text
    investigation_id = created.json()["id"]

    no_tier = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Cannot plan before authorization."})
    assert no_tier.status_code == 409
    authorized = client.post(
        f"/api/salintel/investigations/{investigation_id}/authorize-tier",
        headers=analyst, json={
            "authorized_tier": 1,
            "scope_statement": "Identity, current role, credentials, core relationships, contradictions and known unknowns.",
            "checklist_version": "personnel-assessment-1.0",
            "effort_bounds": {"maximum_human_hours": 2, "chat_cost_allowance_usd": 4},
            "source_categories": ["lawful authorized public records", "member-provided records"],
            "exclusions": ["deep historical networks", "unrestricted personal dossiers"],
            "commercial_treatment": "Separate Proposal",
            "commercial_reference": "SYNTHETIC-PA-T1",
            "investigative_lenses": ["Prevention", "Protection"],
            "reason": "Authorize bounded Tier 1 only."})
    assert authorized.status_code == 200, authorized.text

    plan = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Generate the authorized Tier 1 plan."})
    assert plan.status_code == 200, plan.text
    assert plan.json()["authorized_tier"] == 1 and plan.json()["task_count"] == 8
    assert client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Duplicate must fail."}).status_code == 409

    candidate_one = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates",
        headers=analyst, json={
            "candidate_name": "SYNTHETIC Jordan Taylor",
            "identifiers": {"jurisdiction": "NC", "employer": "Example One"},
            "origin_type": "Chat Research",
            "narrative": "A source-derived candidate requiring human identity resolution."})
    assert candidate_one.status_code == 200, candidate_one.text
    assert candidate_one.json()["identity_collision"] is False
    candidate_two = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates",
        headers=analyst, json={
            "candidate_name": "Synthetic Jordan Taylor",
            "identifiers": {"jurisdiction": "TX", "employer": "Example Two"},
            "origin_type": "Human Investigator",
            "narrative": "A same-name candidate with materially different discriminators."})
    assert candidate_two.status_code == 200, candidate_two.text
    assert candidate_two.json()["identity_collision"] is True

    missing_source = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates/"
        f"{candidate_one.json()['id']}/decision",
        headers=analyst, json={"decision": "Match",
                               "reason": "A match cannot be declared without evidence."})
    assert missing_source.status_code == 409

    material = client.post("/api/materials/upload", headers=analyst, data={
        "title": "SYNTHETIC identity source", "material_kind": "Document",
        "source_origin": "Authorized synthetic issuing record", "sensitivity": "Sensitive",
        "purpose_tags": json.dumps(["SalINTEL", "Personnel Assessment"])},
        files={"file": ("identity.txt", b"SYNTHETIC IDENTITY SOURCE\n", "text/plain")})
    assert material.status_code == 200, material.text
    material_id = material.json()["id"]
    for state, reason in [
        ("Processing", "Begin governed extraction."),
        ("Ready for Human Review", "Source reviewed by a human investigator."),
    ]:
        transitioned = client.post(f"/api/materials/{material_id}/transition",
                                   headers=analyst,
                                   json={"status": state, "reason": reason})
        assert transitioned.status_code == 200, transitioned.text
    linked = client.post(f"/api/materials/{material_id}/links", headers=analyst,
        json={"target_type": "salintel_investigation", "target_id": investigation_id,
              "purpose": "Support identity resolution and claimed-history review."})
    assert linked.status_code == 200, linked.text

    sourced_candidate = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates",
        headers=analyst, json={
            "candidate_name": "SYNTHETIC Jordan Taylor",
            "identifiers": {"jurisdiction": "NC", "record": "SYNTHETIC-001"},
            "origin_type": "Source Extraction",
            "narrative": "Candidate linked to reviewed source material.",
            "source_material_id": material_id})
    assert sourced_candidate.status_code == 200, sourced_candidate.text
    matched = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates/"
        f"{sourced_candidate.json()['id']}/decision",
        headers=analyst, json={"decision": "Match",
                               "reason": "Human analyst reconciled identifiers."})
    assert matched.status_code == 200 and matched.json()["decision"] == "Match"

    forged_fact = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "PA1-IDENTITY", "category": "Identity Resolution",
            "title": "AI-derived claim", "narrative": "Must not become verified fact.",
            "epistemic_state": "Verified Fact", "origin_type": "Chat Research",
            "source_material_id": material_id})
    assert forged_fact.status_code == 409
    verified = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "PA1-IDENTITY", "category": "Identity Resolution",
            "title": "SYNTHETIC identity corroborated",
            "narrative": "Human analyst reconciled the reviewed source and candidate.",
            "epistemic_state": "Verified Fact", "origin_type": "Analyst Assessment",
            "source_reliability": "Reliable", "information_confidence": "High",
            "source_material_id": material_id,
            "protective_intelligence_relevance": True})
    assert verified.status_code == 200, verified.text
    assert verified.json()["qualification_status"] == "Unqualified"
    allegation = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "PA1-CONTRADICTIONS", "category": "Contradictions",
            "title": "SYNTHETIC unresolved report",
            "narrative": "Preserved as an allegation pending corroboration.",
            "epistemic_state": "Unresolved Allegation",
            "origin_type": "Protected Member Input"})
    assert allegation.status_code == 200, allegation.text
    out_of_tier = client.post(
        f"/api/salintel/personnel-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "PA2-INSIDER", "category": "Insider-Threat Relevance",
            "title": "Out of scope", "narrative": "Tier 2 work must not enter Tier 1.",
            "epistemic_state": "Analyst Judgment", "origin_type": "Analyst Assessment"})
    assert out_of_tier.status_code == 409

    detail = client.get(
        f"/api/salintel/personnel-assessments/{investigation_id}",
        headers=analyst)
    assert detail.status_code == 200, detail.text
    assert detail.json()["identity_collision"] is True
    assert detail.json()["identity_resolution_status"] == "Partially Resolved"
    assert detail.json()["progress"] == {"total": 8, "addressed": 2, "open": 6}
    assert len(detail.json()["findings"]) == 2
    assert detail.json()["completion_readiness"]["ready"] is False
    assert client.post(
        f"/api/salintel/investigations/{investigation_id}/complete-tier",
        headers=analyst, json={
            "tier": 1,
            "completion_statement": "Must not bypass the Personnel closure gate.",
            "residual_unknowns": "Open authorized requirements remain.",
        }).status_code == 409
    assert client.get(
        f"/api/salintel/personnel-assessments/{investigation_id}",
        headers=member).status_code == 403

    for candidate_id in (candidate_one.json()["id"], candidate_two.json()["id"]):
        decided = client.post(
            f"/api/salintel/personnel-assessments/{investigation_id}/identity-candidates/"
            f"{candidate_id}/decision",
            headers=analyst, json={
                "decision": "Excluded",
                "reason": "Human analyst resolved the same-name collision using governed discriminators.",
            })
        assert decided.status_code == 200, decided.text

    addressed = {"PA1-IDENTITY", "PA1-CONTRADICTIONS"}
    for requirement in checklist.json()["tiers"]:
        if requirement["tier_required"] > 1 or requirement["key"] in addressed:
            continue
        is_unknown = requirement["key"] == "PA1-UNKNOWNS"
        finding = client.post(
            f"/api/salintel/personnel-assessments/{investigation_id}/findings",
            headers=analyst, json={
                "checklist_key": requirement["key"],
                "category": requirement["category"],
                "title": f"SYNTHETIC bounded finding for {requirement['key']}",
                "narrative": (
                    "The authorized Tier 1 collection is documented as complete within its bounds; "
                    "deeper or unavailable-source questions remain governed for follow-on review."
                ),
                "epistemic_state": "Information Gap" if is_unknown else "Analyst Judgment",
                "origin_type": "Analyst Assessment",
                "source_reliability": "Not Assessed",
                "information_confidence": "Moderate",
            })
        assert finding.status_code == 200, finding.text

    research_plan = client.post(
        f"/api/salintel/investigations/{investigation_id}/research-plans",
        headers=analyst, json={
            "reason": "Authorize the shared Chat-led and mixed-source plan before tier closure."
        })
    assert research_plan.status_code == 200, research_plan.text
    research_plan_id = research_plan.json()["id"]
    research = client.get(
        f"/api/salintel/investigations/{investigation_id}/research", headers=analyst
    ).json()
    chat_task = next(task for task in research["tasks"]
                     if task["contributor"] == "Chat Research")
    material = client.post("/api/materials/upload", headers=analyst, data={
        "title": "SYNTHETIC Personnel closure source",
        "material_kind": "Document",
        "source_origin": "Authorized synthetic public record",
        "sensitivity": "Sensitive",
        "purpose_tags": json.dumps(["SalINTEL", "Personnel Assessment"])},
        files={"file": ("personnel-closure-source.txt",
                         b"SYNTHETIC PERSONNEL CLOSURE SOURCE\n", "text/plain")})
    assert material.status_code == 200, material.text
    material_id = material.json()["id"]
    for status, reason in (("Processing", "Begin governed processing."),
                           ("Ready for Human Review", "Source capture reviewed.")):
        transition = client.post(f"/api/materials/{material_id}/transition",
            headers=analyst, json={"status": status, "reason": reason})
        assert transition.status_code == 200, transition.text
    linked = client.post(f"/api/materials/{material_id}/links", headers=analyst,
        json={"target_type": "salintel_investigation", "target_id": investigation_id,
              "purpose": "Support source-grounded Chat research and closure."})
    assert linked.status_code == 200, linked.text
    accessed = client.post(
        f"/api/salintel/investigations/{investigation_id}/research-plans/"
        f"{research_plan_id}/source-results", headers=analyst, json={
            "task_key": chat_task["task_key"], "outcome": "Accessed",
            "source_title": "SYNTHETIC authoritative personnel source",
            "source_locator": "https://example.invalid/personnel-closure-source",
            "notes": "Chat accessed and reconciled the governed synthetic source.",
            "source_reliability": "Reliable", "information_confidence": "Moderate",
            "source_material_id": material_id})
    assert accessed.status_code == 200, accessed.text
    accessed_id = accessed.json()["id"]
    outcome_for = {
        "Chat Research": "Unavailable",
        "Salus Human Investigator": "Requires Human Collection",
        "Protected Member / Form": "Requires Protected Member Input",
        "Document / Material": "Unavailable",
        "Prior SalCAPA Context": "Unavailable",
        "Approved Partner Return": "Requires Partner Authorization",
    }
    for task in research["tasks"]:
        if task["task_key"] == chat_task["task_key"]:
            continue
        result = client.post(
            f"/api/salintel/investigations/{investigation_id}/research-plans/"
            f"{research_plan_id}/source-results", headers=analyst, json={
                "task_key": task["task_key"],
                "outcome": outcome_for[task["contributor"]],
                "source_title": f"SYNTHETIC disposition for {task['task_key']}",
                "notes": "Truthful bounded stopping point or collection requirement."})
        assert result.status_code == 200, result.text
    product = client.post(
        f"/api/salintel/investigations/{investigation_id}/research-plans/"
        f"{research_plan_id}/products", headers=analyst, json={
            "executive_summary": "Chat completed the authorized bounded research and reconciled collection needs.",
            "findings": [{
                "statement": "The synthetic source reports an authorized personnel association.",
                "epistemic_state": "Reported Information",
                "source_result_ids": [accessed_id],
                "information_confidence": "Moderate",
                "implications": "Human qualification remains controlling."}],
            "known_unknowns": "Unavailable and human-collection requirements remain governed.",
            "completion_statement": "The bounded Chat research scope is complete."})
    assert product.status_code == 200, product.text
    reviewed = client.post(
        f"/api/salintel/investigations/{investigation_id}/research-products/"
        f"{product.json()['id']}/review", headers=analyst, json={
            "status": "Qualified",
            "reason": "Salus reviewed sources, distinctions, contradictions, and stopping points."})
    assert reviewed.status_code == 200, reviewed.text

    qualified = client.post(
        f"/api/salintel/investigations/{investigation_id}/qualify",
        headers=analyst, json={
            "status": "Qualified",
            "reason": "Human reviewer challenged the evidence, dispositions, and bounded stopping point.",
        })
    assert qualified.status_code == 200, qualified.text
    ready = client.get(
        f"/api/salintel/personnel-assessments/{investigation_id}", headers=analyst)
    assert ready.status_code == 200, ready.text
    assert ready.json()["progress"] == {"total": 8, "addressed": 8, "open": 0}
    assert ready.json()["identity_resolution_status"] == "Resolved"
    assert ready.json()["completion_readiness"]["chat_sources_accessed"] >= 1
    assert ready.json()["completion_readiness"]["qualified_research_product_count"] >= 1
    assert ready.json()["completion_readiness"]["ready"] is True

    completed = client.post(
        f"/api/salintel/investigations/{investigation_id}/complete-tier",
        headers=analyst, json={
            "tier": 1,
            "completion_statement": (
                "The authorized Tier 1 baseline scope is complete; findings remain bounded by the "
                "approved sources, purpose, and effort authorization."
            ),
            "residual_unknowns": (
                "Unavailable and deeper-source questions are recorded in PA1-UNKNOWNS and require "
                "separate authorization before any broader collection."
            ),
        })
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "Tier Complete"
    assert completed.json()["completed_tier"] == 1
    assert client.post(
        f"/api/salintel/investigations/{investigation_id}/complete-tier",
        headers=analyst, json={
            "tier": 1, "completion_statement": "Duplicate completion must fail.",
            "residual_unknowns": "Already governed.",
        }).status_code == 409
    assert client.post(
        f"/api/salintel/investigations/{investigation_id}/complete-tier",
        headers=member, json={
            "tier": 1, "completion_statement": "Member-forged completion must fail.",
            "residual_unknowns": "Unauthorized.",
        }).status_code == 403

    conn = app.db()
    records = collect_tenant_records(conn, 1)
    before = len(records["salintel_investigation_items"])
    replace_tenant_records(conn, 1, records)
    conn.commit()
    after = conn.execute(
        "SELECT COUNT(*) c FROM salintel_investigation_items WHERE tenant_id=1"
    ).fetchone()["c"]
    assert after == before
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) "
                 "VALUES(2,'Other Tenant','other-tenant-pa','Active',?) "
                 "ON CONFLICT(id) DO NOTHING", (app.now(),))
    conn.commit(); conn.close()
    other = {**analyst, "X-Salus-Tenant": "2", "X-Salus-User": "Other Analyst"}
    assert client.get(
        f"/api/salintel/personnel-assessments/{investigation_id}",
        headers=other).status_code == 403

    events = client.get(f"/api/salintel/investigations/{investigation_id}",
                        headers=analyst).json()["events"]
    versions = [row["version_no"] for row in events]
    assert versions == list(range(1, len(versions) + 1))
    assert any(row["event_type"] == "PERSONNEL_RESEARCH_PLAN_CREATED" for row in events)
    assert any(row["event_type"] == "PERSONNEL_IDENTITY_DECIDED" for row in events)
    assert any(row["event_type"] == "TIER_COMPLETED" for row in events)
    print("SALCAPA_PERSONNEL_ASSESSMENT_PASS", app.DB_BACKEND)


if __name__ == "__main__":
    main()
