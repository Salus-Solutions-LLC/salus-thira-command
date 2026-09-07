#!/usr/bin/env python3
"""Acceptance checks for the governed Facility Assessment foundation."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "facility.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from portable_backup import collect_tenant_records, replace_tenant_records


def main():
    client = TestClient(salcapa_runtime.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "Facility Analyst",
               "X-Salus-Clearance": "Highly Sensitive"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member User"}

    checklist = client.get("/api/salintel/facility-assessment/checklist", headers=analyst)
    assert checklist.status_code == 200, checklist.text
    assert checklist.json()["version"] == "facility-assessment-1.0"
    assert {row["tier_required"] for row in checklist.json()["tiers"]} == {1, 2, 3}
    assert client.get("/api/salintel/facility-assessment/checklist",
                      headers=member).status_code == 403

    created = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "facility-assessment",
        "title": "SYNTHETIC Facility Assessment",
        "subject_reference": "SYNTHETIC-FACILITY-001",
        "purpose": "Defensive synthetic continuity and protective assessment.",
        "requested_tier": 1, "sensitivity": "Sensitive"})
    assert created.status_code == 200, created.text
    investigation_id = created.json()["id"]

    no_tier = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Planning before authorization must fail."})
    assert no_tier.status_code == 409
    authorized = client.post(
        f"/api/salintel/investigations/{investigation_id}/authorize-tier",
        headers=analyst, json={
            "authorized_tier": 1,
            "scope_statement": "Facility context, essential functions, baseline conditions, controls, alternates and known unknowns.",
            "checklist_version": "facility-assessment-1.0",
            "effort_bounds": {"maximum_human_hours": 4, "chat_cost_allowance_usd": 6},
            "source_categories": ["authorized public records", "member-provided records",
                                  "approved site observations"],
            "exclusions": ["intrusive testing", "offensive analysis", "Tier 2 deep dive"],
            "commercial_treatment": "Separate Proposal",
            "commercial_reference": "SYNTHETIC-FA-T1",
            "investigative_lenses": ["Prevention", "Protection", "Mitigation",
                                     "Response", "Recovery"],
            "reason": "Authorize bounded defensive Tier 1 only."})
    assert authorized.status_code == 200, authorized.text

    plan = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Generate bounded Tier 1 facility plan."})
    assert plan.status_code == 200, plan.text
    assert plan.json()["authorized_tier"] == 1
    assert plan.json()["requirement_count"] == 11
    assert client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/research-plan",
        headers=analyst, json={"reason": "Duplicate must fail."}).status_code == 409

    context = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/context",
        headers=analyst, json={
            "facility_name": "SYNTHETIC Operations Center",
            "facility_reference": "SYNTHETIC-SITE-001",
            "location_context": "Synthetic location used only for deterministic testing.",
            "mission_summary": "Coordinates time-sensitive protective and continuity functions.",
            "jurisdiction": "Synthetic Jurisdiction",
            "geographic_bounds": "Authorized synthetic test boundary."})
    assert context.status_code == 200, context.text
    assert context.json()["context_version"] == 1
    forged_context = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/context",
        headers=analyst, json={
            "facility_name": "Forged", "facility_reference": "FORGED",
            "location_context": "Must fail.", "mission_summary": "Must fail.",
            "qualification_status": "Qualified"})
    assert forged_context.status_code == 422

    material = client.post("/api/materials/upload", headers=analyst, data={
        "title": "SYNTHETIC facility source", "material_kind": "Document",
        "source_origin": "Authorized synthetic facility record", "sensitivity": "Sensitive",
        "purpose_tags": json.dumps(["SalINTEL", "Facility Assessment"])},
        files={"file": ("facility.txt", b"SYNTHETIC FACILITY SOURCE\n", "text/plain")})
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
              "purpose": "Support defensive facility and essential-function analysis."})
    assert linked.status_code == 200, linked.text

    invalid_coordinate = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/geospatial-features",
        headers=analyst, json={
            "title": "Invalid location", "category": "Facility Location",
            "geometry_type": "Point", "coordinates": [[-98.4, 95.0]],
            "description": "Invalid latitude must fail.", "spatial_precision": "Exact",
            "origin_type": "Analyst Assessment", "epistemic_state": "Verified Fact",
            "source_material_id": material_id})
    assert invalid_coordinate.status_code == 422
    forged_geospatial = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/geospatial-features",
        headers=analyst, json={
            "title": "Forged release", "category": "Facility Location",
            "geometry_type": "Point", "coordinates": [[-98.4936, 29.4241]],
            "description": "Client authority fields must fail.", "spatial_precision": "Exact",
            "origin_type": "Analyst Assessment", "epistemic_state": "Verified Fact",
            "source_material_id": material_id, "member_disclosure_authorized": True})
    assert forged_geospatial.status_code == 422
    open_area = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/geospatial-features",
        headers=analyst, json={
            "title": "Open boundary", "category": "Authorized Assessment Boundary",
            "geometry_type": "Area",
            "coordinates": [[-98.50, 29.42], [-98.49, 29.42], [-98.49, 29.43]],
            "description": "An unclosed area must fail.", "spatial_precision": "Generalized",
            "location_date": "2026-09-07", "origin_type": "Analyst Assessment",
            "epistemic_state": "Analyst Judgment", "source_material_id": material_id})
    assert open_area.status_code == 422
    location = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/geospatial-features",
        headers=analyst, json={
            "title": "SYNTHETIC facility location", "category": "Facility Location",
            "geometry_type": "Point", "coordinates": [[-98.4936, 29.4241]],
            "description": "Synthetic point used only for deterministic acceptance.",
            "jurisdiction": "Synthetic Jurisdiction", "location_date": "2026-09-07",
            "spatial_precision": "Exact", "origin_type": "Analyst Assessment",
            "epistemic_state": "Verified Fact", "source_reliability": "High",
            "information_confidence": "High", "source_material_id": material_id})
    assert location.status_code == 200, location.text
    assert location.json()["coordinate_reference_system"] == "WGS84 / EPSG:4326"
    assert location.json()["member_disclosure_authorized"] is False
    boundary_coordinates = [
        [-98.5000, 29.4200], [-98.4870, 29.4200], [-98.4870, 29.4300],
        [-98.5000, 29.4300], [-98.5000, 29.4200],
    ]
    boundary = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/geospatial-features",
        headers=analyst, json={
            "title": "SYNTHETIC authorized assessment boundary",
            "category": "Authorized Assessment Boundary", "geometry_type": "Area",
            "coordinates": boundary_coordinates,
            "description": "Generalized synthetic boundary for the authorized scope.",
            "jurisdiction": "Synthetic Jurisdiction", "location_date": "2026-09-07",
            "spatial_precision": "Generalized", "origin_type": "Analyst Assessment",
            "epistemic_state": "Analyst Judgment", "source_reliability": "High",
            "information_confidence": "Moderate", "source_material_id": material_id})
    assert boundary.status_code == 200, boundary.text
    assert boundary.json()["coordinate_count"] == 5
    assert boundary.json()["operational_authority_granted"] is False

    forged_fact = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/essential-functions",
        headers=analyst, json={
            "title": "Coordination", "mission_statement": "Coordinate field support.",
            "criticality_basis": "Time-sensitive support.", "origin_type": "Chat Research",
            "epistemic_state": "Verified Fact", "source_material_id": material_id})
    assert forged_fact.status_code == 409
    function = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/essential-functions",
        headers=analyst, json={
            "title": "Coordination", "mission_statement": "Coordinate field support.",
            "criticality_basis": "Delay would affect time-sensitive protective decisions.",
            "maximum_tolerable_disruption": "Synthetic test value",
            "origin_type": "Analyst Assessment", "epistemic_state": "Verified Fact",
            "source_material_id": material_id})
    assert function.status_code == 200, function.text
    function_id = function.json()["id"]

    non_defensive = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/essential-functions/"
        f"{function_id}/dependency-analysis", headers=analyst, json={
            "analysis_mode": "Offensive", "dependency": "Communications",
            "failure_mode_type": "Intentional / Adversarial", "failure_mode": "Disruption",
            "preventive_controls": "Governed controls", "detection": "Authorized monitoring",
            "consequences": "Delayed coordination", "alternate_capability": "Alternate channel",
            "restoration_requirement": "Restore authorized service",
            "origin_type": "Analyst Assessment", "epistemic_state": "Analyst Judgment"})
    assert non_defensive.status_code == 422
    forged_authority = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/essential-functions/"
        f"{function_id}/dependency-analysis", headers=analyst, json={
            "analysis_mode": "Defensive", "dependency": "Communications",
            "failure_mode_type": "Intentional / Adversarial", "failure_mode": "Disruption",
            "preventive_controls": "Governed controls", "detection": "Authorized monitoring",
            "consequences": "Delayed coordination", "alternate_capability": "Alternate channel",
            "restoration_requirement": "Restore authorized service",
            "origin_type": "Analyst Assessment", "epistemic_state": "Analyst Judgment",
            "operational_authority_granted": True})
    assert forged_authority.status_code == 422
    chain = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/essential-functions/"
        f"{function_id}/dependency-analysis", headers=analyst, json={
            "analysis_mode": "Defensive", "dependency": "Communications service",
            "failure_mode_type": "Intentional / Adversarial",
            "failure_mode": "Defensive scenario: unauthorized disruption of service.",
            "preventive_controls": "Access governance and approved resilience controls.",
            "detection": "Authorized service-health and anomaly monitoring.",
            "consequences": "Delayed coordination and increased manual workload.",
            "alternate_capability": "Approved alternate communications channel.",
            "restoration_requirement": "Validate service integrity before restoration.",
            "origin_type": "Analyst Assessment", "epistemic_state": "Analyst Judgment",
            "source_material_id": material_id, "insider_threat_relevance": True,
            "emergency_exploitation_relevance": True,
            "competing_resource_relevance": True,
            "intentional_scenario_types": [
                "Sabotage", "Active-Assailant", "Insider-Enabled Disruption",
                "Coordinated Cyber-Physical Incident", "Deliberate Fire or Destructive Act",
                "Theft or Diversion", "Supply-Chain Interference", "Workplace Violence",
                "Attack Timed with Emergency", "Exploitation of Degraded Conditions"]})
    assert chain.status_code == 200, chain.text
    assert chain.json()["analysis_mode"] == "Defensive"
    assert chain.json()["operational_authority_granted"] is False

    out_of_tier = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "FA2-INSIDER", "category": "Insider-Threat Relevance",
            "title": "Out of scope", "narrative": "Tier 2 work cannot enter Tier 1.",
            "epistemic_state": "Analyst Judgment", "origin_type": "Analyst Assessment"})
    assert out_of_tier.status_code == 409
    unknown = client.post(
        f"/api/salintel/facility-assessments/{investigation_id}/findings",
        headers=analyst, json={
            "checklist_key": "FA1-UNKNOWNS", "category": "Known Unknowns and Reassessment",
            "title": "SYNTHETIC restoration evidence gap",
            "narrative": "Current restoration validation evidence is unavailable.",
            "epistemic_state": "Information Gap", "origin_type": "Human Investigator",
            "reassessment_trigger": "New approved restoration test evidence becomes available."})
    assert unknown.status_code == 200, unknown.text
    assert unknown.json()["member_disclosure_authorized"] is False

    detail = client.get(
        f"/api/salintel/facility-assessments/{investigation_id}", headers=analyst)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert len(body["context_history"]) == 1
    assert len(body["geospatial_features"]) == 2
    assert body["geospatial_summary"] == {
        "feature_count": 2, "point_count": 1, "path_count": 0, "area_count": 1,
        "external_map_transmission": False,
        "coordinate_reference_system": "WGS84 / EPSG:4326",
    }
    assert len(body["essential_functions"]) == 1
    assert len(body["dependency_analyses"]) == 1
    assert body["dependency_analyses"][0]["structured_detail"]["chain_order"] == [
        "mission_function", "dependency", "failure_mode", "preventive_controls",
        "detection", "consequences", "alternate_capability", "restoration_requirement"]
    assert body["governance"]["salus_only"] is True
    assert body["governance"]["operational_authority_granted"] is False
    assert body["completion_readiness"]["ready"] is False
    assert any("natural, accidental, and intentional" in blocker
               for blocker in body["completion_readiness"]["blockers"])
    assert not any("facility-location point" in blocker
                   for blocker in body["completion_readiness"]["blockers"])
    assert not any("assessment-boundary area" in blocker
                   for blocker in body["completion_readiness"]["blockers"])
    blocked_completion = client.post(
        f"/api/salintel/investigations/{investigation_id}/complete-tier",
        headers=analyst, json={
            "tier": 1,
            "completion_statement": "Must not bypass the Facility closure gate.",
            "residual_unknowns": "Open authorized requirements remain."})
    assert blocked_completion.status_code == 409, blocked_completion.text
    assert client.get(
        f"/api/salintel/facility-assessments/{investigation_id}",
        headers=member).status_code == 403

    other_tenant = dict(analyst)
    other_tenant["X-Salus-Tenant"] = "2"
    assert client.get(
        f"/api/salintel/facility-assessments/{investigation_id}",
        headers=other_tenant).status_code in (403, 404)

    conn = salcapa_runtime.core.db()
    try:
        actions = {row["action"] for row in conn.execute(
            "SELECT action FROM audit_log WHERE tenant_id=? AND entity_type='facility_assessment'",
            (1,))}
        assert {"FACILITY_RESEARCH_PLAN_CREATED", "FACILITY_CONTEXT_RECORDED",
                "FACILITY_GEOSPATIAL_FEATURE_RECORDED",
                "FACILITY_ESSENTIAL_FUNCTION_RECORDED",
                "FACILITY_DEPENDENCY_CHAIN_RECORDED", "FACILITY_FINDING_RECORDED"} <= actions
        records = collect_tenant_records(conn, 1)
        assert any(row["id"] == investigation_id
                   for row in records["salintel_investigations"])
        item_count = len([row for row in records["salintel_investigation_items"]
                          if row["investigation_id"] == investigation_id])
        assert item_count >= 15
        replace_tenant_records(conn, 1, records)
        restored = conn.execute(
            "SELECT COUNT(*) c FROM salintel_investigation_items WHERE tenant_id=? "
            "AND investigation_id=?", (1, investigation_id)).fetchone()["c"]
        assert restored == item_count
    finally:
        conn.close()

    print("Facility Assessment governed foundation acceptance passed")


if __name__ == "__main__":
    main()
