#!/usr/bin/env python3
"""Acceptance checks for governed, versioned SalINTEL recurring monitoring."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "monitoring.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from portable_backup import collect_tenant_records, replace_tenant_records, validate_records


def main():
    client = TestClient(salcapa_runtime.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "Monitoring Supervisor",
               "X-Salus-Clearance": "Highly Sensitive"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member Requester",
              "X-Salus-Clearance": "Sensitive"}
    other = {"X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
             "X-Salus-User": "Other Tenant", "X-Salus-Clearance": "Highly Sensitive"}

    assert client.get("/api/system/mode").json()["version"] == "3.62"
    root = client.get("/")
    assert root.status_code == 200
    assert "/static/product-version.js" in root.text
    assert "/static/salcapa-display.js" in root.text
    operating_model = client.get("/api/salcapa/common-operating-picture", headers=analyst).json()[
        "protective_readiness"
    ]
    assert [stage["key"] for stage in operating_model["stages"]] == [
        "see", "decide", "coordinate", "act", "prove"
    ]
    assert operating_model["functional_ownership"] == {
        "see": "SalINTEL™", "decide": "SalTHIRA™ plus authorized decision-makers",
        "coordinate": "SalCAPA™", "act": "SalOPS™", "prove": "Cross-cutting assurance",
    }

    created = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "organizations", "title": "SYNTHETIC monitoring baseline",
        "subject_reference": "SYNTHETIC-ORG-WATCH-001",
        "purpose": "Lawful synthetic recurring-monitoring acceptance.",
        "requested_tier": 1, "sensitivity": "Standard"})
    assert created.status_code == 200, created.text
    record_id = created.json()["id"]

    default_no = client.post(
        f"/api/salintel/investigations/{record_id}/monitoring-selection",
        headers=analyst, json={})
    assert default_no.status_code == 200, default_no.text
    assert default_no.json()["explicit_selection"] == "No"
    assert default_no.json()["status"] == "Not Requested"
    assert default_no.json()["charge_created"] is False

    forged = client.post(
        f"/api/salintel/investigations/{record_id}/monitoring-selection",
        headers=analyst, json={"recurring_monitoring": "Yes", "purpose": "Watch",
        "requested_scope": "Approved public-source changes.",
        "requested_cadence": "Weekly", "status": "Active", "approved_by": "Client"})
    assert forged.status_code == 422
    incomplete = client.post(
        f"/api/salintel/investigations/{record_id}/monitoring-selection",
        headers=analyst, json={"recurring_monitoring": "Yes"})
    assert incomplete.status_code == 422
    assert client.get(f"/api/salintel/investigations/{record_id}/monitoring",
                      headers=member).status_code == 403
    assert client.get(f"/api/salintel/investigations/{record_id}/monitoring",
                      headers=other).status_code == 403

    # Establish a disclosed completed baseline only for Protected Member request testing.
    conn = salcapa_runtime.core.db()
    conn.execute("UPDATE salintel_investigations SET status='Tier Complete',"
                 "qualification_status='Qualified',authorized_tier=1,completed_tier=1,"
                 "disclosure_status='Approved for Tenant' WHERE id=?", (record_id,))
    conn.commit(); conn.close()

    request = client.post(
        f"/api/salintel/investigations/{record_id}/monitoring-selection",
        headers=member, json={"recurring_monitoring": "Yes",
        "purpose": "Watch material changes affecting protected operations.",
        "requested_scope": "Documented organizational status and service changes.",
        "requested_cadence": "Weekly", "requested_start_date": "2026-09-08",
        "source_categories": ["lawful public sources"],
        "exclusions": ["personal financial dossiers"],
        "questions": ["Has ownership or operational capacity materially changed?"],
        "known_unknowns": ["Unpublished continuity arrangements"],
        "indicators": ["regulatory filing", "service interruption"],
        "watch_terms": ["SYNTHETIC ORG"], "entities": ["SYNTHETIC ORG"],
        "relationships": ["supplies protected operation"],
        "dependencies": ["essential service"],
        "geographic_bounds": "United States", "jurisdiction_bounds": "Federal and state",
        "language_bounds": "English", "change_thresholds": "Verified control or service change.",
        "escalation_criteria": "Credible immediate continuity impact.",
        "partner_support_requested": False, "commercial_preference": "Not Determined"})
    assert request.status_code == 200, request.text
    profile_key = request.json()["profile_key"]
    assert request.json()["status"] == "Awaiting Salus Approval"
    assert request.json()["baseline_tier_reference"] == 1
    assert request.json()["tier_change_authorized"] is False
    assert request.json()["member_release_authorized"] is False

    duplicate = client.post(
        f"/api/salintel/investigations/{record_id}/monitoring-selection",
        headers=analyst, json={"recurring_monitoring": "Yes", "purpose": "Duplicate",
        "requested_scope": "Duplicate watch.", "requested_cadence": "Monthly"})
    assert duplicate.status_code == 409
    approval_path = f"/api/salintel/investigations/{record_id}/monitoring/{profile_key}/approve"
    approval = {"approved_scope": "Bounded documented organizational and service changes.",
        "cadence": "Weekly", "cadence_detail": "Each Tuesday after 09:00 UTC",
        "start_date": "2020-09-08", "end_date": "2027-09-08",
        "renewal_date": "2027-08-08", "approved_sources": ["lawful public sources"],
        "exclusions": ["personal financial dossiers"],
        "questions": ["Has ownership or capacity materially changed?"],
        "known_unknowns": ["Unpublished continuity arrangements"],
        "indicators": ["regulatory filing", "service interruption"],
        "watch_terms": ["SYNTHETIC ORG"], "entities": ["SYNTHETIC ORG"],
        "relationships": ["supplies protected operation"], "dependencies": ["essential service"],
        "geographic_bounds": "United States", "jurisdiction_bounds": "Federal and state",
        "language_bounds": "English", "change_thresholds": "Verified control or service change.",
        "escalation_criteria": "Credible immediate continuity impact.",
        "review_requirements": "Authorized Salus human review every cycle.",
        "member_notification_policy": "Explicit Salus release decision before member notice.",
        "member_release_permitted": False, "global_partner_eligible": False,
        "commercial_treatment": "Included", "commercial_reference": "SYNTHETIC-TERMS",
        "approval_reason": "Approved bounded no-cost synthetic watch."}
    assert client.post(approval_path, headers=member, json=approval).status_code == 403
    approved = client.post(approval_path, headers=analyst, json=approval)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "Active" and approved.json()["version_no"] == 2
    assert approved.json()["charge_created"] is False
    assert approved.json()["external_escalation_authorized"] is False
    assert client.post(approval_path, headers=analyst, json=approval).status_code == 409

    material = client.post("/api/materials/upload", headers=analyst, data={
        "title": "SYNTHETIC ORG continuity monitoring source",
        "material_kind": "Document", "source_origin": "Authorized synthetic public record",
        "sensitivity": "Standard",
        "purpose_tags": json.dumps([
            "SalINTEL", "Recurring Monitoring", "lawful public sources"])},
        files={"file": ("monitoring-source.txt", b"SYNTHETIC ORG MONITORING SOURCE\n", "text/plain")})
    assert material.status_code == 200, material.text
    material_id = material.json()["id"]
    for state, reason in (("Processing", "Begin extraction."),
                          ("Ready for Human Review", "Human reviewed monitoring source.")):
        transitioned = client.post(f"/api/materials/{material_id}/transition",
            headers=analyst, json={"status": state, "reason": reason})
        assert transitioned.status_code == 200, transitioned.text
    linked = client.post(f"/api/materials/{material_id}/links", headers=analyst,
        json={"target_type": "salintel_investigation", "target_id": record_id,
              "purpose": "Governed recurring-monitoring source reuse by reference."})
    assert linked.status_code == 200, linked.text

    cycle_path = f"/api/salintel/investigations/{record_id}/monitoring/{profile_key}/cycles"
    assert client.post(cycle_path, headers=member, json={"reason": "Bypass."}).status_code == 403
    assert client.post(cycle_path, headers=analyst, json={
        "reason": "Attempt forged state.", "outcome": "No Material Change"}).status_code == 422
    cycle = client.post(cycle_path, headers=analyst, json={
        "reason": "Execute approved internal linked-material monitoring research."})
    assert cycle.status_code == 200, cycle.text
    cycle_id = cycle.json()["id"]
    assert cycle.json()["matched_material_ids"] == [material_id]
    assert cycle.json()["source_access_records"][0]["outcome"] == "Accessed"
    assert cycle.json()["source_bytes_duplicated"] is False
    assert cycle.json()["external_network_accessed"] is False
    assert client.post(cycle_path, headers=analyst, json={"reason": "Duplicate."}).status_code == 409

    outcome_path = f"{cycle_path}/{cycle_id}/outcome"
    forged_outcome = client.post(outcome_path, headers=analyst, json={
        "outcome": "New Information", "narrative": "Attempt unaccessed evidence.",
        "evidence_material_ids": [material_id + 999]})
    assert forged_outcome.status_code == 409
    outcome = client.post(outcome_path, headers=analyst, json={
        "outcome": "New Information",
        "narrative": "The governed source adds relevant information without changing the qualified baseline.",
        "findings": [{"statement": "Source requires Salus qualification.",
                      "epistemic_state": "Reported Information",
                      "material_ids": [material_id]}],
        "corroboration": [], "contradictions": [],
        "new_known_unknowns": ["Current continuity arrangement remains unpublished."],
        "resolved_known_unknowns": [], "changed_relationships": [],
        "changed_dependencies": [], "weak_signals": [], "anomalies": [],
        "implications": ["Retain in the Salus review queue."],
        "evidence_material_ids": [material_id],
        "recommend_new_investigation": False, "recommend_deeper_tier": False})
    assert outcome.status_code == 200, outcome.text
    assert outcome.json()["review_status"] == "Awaiting Salus Review"
    assert outcome.json()["member_release_authorized"] is False
    assert outcome.json()["charge_created"] is False
    outcome_id = outcome.json()["id"]
    notification_id = outcome.json()["notification_id"]
    review_path = (
        f"/api/salintel/investigations/{record_id}/monitoring/{profile_key}"
        f"/outcomes/{outcome_id}/review"
    )
    forged_review = client.post(review_path, headers=analyst, json={
        "decision": "Qualified", "reason": "Attempt forged authority.",
        "member_release_authorized": True})
    assert forged_review.status_code == 422
    assert client.post(review_path, headers=member, json={
        "decision": "Qualified", "reason": "Member cannot qualify."}).status_code == 403
    reviewed = client.post(review_path, headers=analyst, json={
        "decision": "Qualified", "reason": "Evidence and distinctions reviewed by Salus."})
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["human_qualified"] is True
    assert reviewed.json()["member_release_authorized"] is False
    assert reviewed.json()["source_outcome_preserved_unchanged"] is True
    assert client.post(review_path, headers=analyst, json={
        "decision": "Rejected", "reason": "Duplicate review."}).status_code == 409
    acknowledgement_path = (
        f"/api/salintel/investigations/{record_id}/monitoring/{profile_key}"
        f"/notifications/{notification_id}/acknowledge"
    )
    assert client.post(acknowledgement_path, headers=member, json={
        "reason": "Member cannot acknowledge internal notice."}).status_code == 403
    acknowledgement = client.post(acknowledgement_path, headers=analyst, json={
        "reason": "Received in the governed Salus review queue."})
    assert acknowledgement.status_code == 200, acknowledgement.text
    assert acknowledgement.json()["status"] == "Acknowledged"
    assert acknowledgement.json()["external_notification_sent"] is False
    assert acknowledgement.json()["source_notification_preserved_unchanged"] is True
    assert client.post(acknowledgement_path, headers=analyst, json={
        "reason": "Duplicate acknowledgement."}).status_code == 409
    assert client.post(outcome_path, headers=analyst, json={
        "outcome": "No Material Change", "narrative": "Duplicate.",
        "evidence_material_ids": []}).status_code == 409

    assert client.post(cycle_path, headers=analyst, json={
        "reason": "Attempt early cycle without explicit decision."}).status_code == 409
    cycle_two = client.post(cycle_path, headers=analyst, json={
        "reason": "Authorize early in-scope comparison cycle.",
        "execute_before_due": True})
    assert cycle_two.status_code == 200, cycle_two.text
    assert cycle_two.json()["prior_execution_id"] == cycle_id
    assert cycle_two.json()["prior_outcome"] == "New Information"
    no_change = client.post(f"{cycle_path}/{cycle_two.json()['id']}/outcome",
        headers=analyst, json={"outcome": "No Material Change",
        "narrative": "Research completed against accessed material; no material change identified.",
        "evidence_material_ids": [material_id]})
    assert no_change.status_code == 200, no_change.text
    assert no_change.json()["next_research_date"]

    path = f"/api/salintel/investigations/{record_id}/monitoring/{profile_key}/transition"
    paused = client.post(path, headers=analyst, json={"action": "Pause", "reason": "Review cadence."})
    assert paused.status_code == 200 and paused.json()["status"] == "Paused"
    resumed = client.post(path, headers=analyst, json={"action": "Resume", "reason": "Review complete."})
    assert resumed.status_code == 200 and resumed.json()["status"] == "Active"
    ended = client.post(path, headers=analyst, json={"action": "End", "reason": "Approved term ended."})
    assert ended.status_code == 200 and ended.json()["status"] == "Completed"
    assert client.post(path, headers=analyst, json={"action": "Resume", "reason": "Forgery."}).status_code == 409

    view = client.get(f"/api/salintel/investigations/{record_id}/monitoring", headers=analyst)
    assert view.status_code == 200, view.text
    data = view.json()
    assert len(next(x for x in data["profiles"] if x["profile_key"] == profile_key)) > 10
    history = [x for x in data["version_history"] if x["profile_key"] == profile_key]
    assert [x["version_no"] for x in history] == [1, 2, 3, 4, 5]
    assert data["automatic_charges"] is False and data["automatic_disclosure"] is False
    assert len(data["cycle_executions"]) == 2
    assert [item["outcome"] for item in data["cycle_outcomes"]] == [
        "New Information", "No Material Change"]
    assert len(data["review_notifications"]) == 2
    assert len(data["outcome_reviews"]) == 1
    assert data["outcome_reviews"][0]["decision"] == "Qualified"
    assert len(data["notification_acknowledgements"]) == 1
    member_data = client.get(
        f"/api/salintel/investigations/{record_id}/monitoring", headers=member).json()
    assert member_data["cycle_executions"] == []
    assert member_data["cycle_outcomes"] == []
    assert member_data["review_notifications"] == []
    assert member_data["outcome_reviews"] == []
    assert member_data["notification_acknowledgements"] == []

    conn = salcapa_runtime.core.db()
    record = conn.execute("SELECT * FROM salintel_investigations WHERE id=?", (record_id,)).fetchone()
    assert record["authorized_tier"] == 1 and record["completed_tier"] == 1
    records = collect_tenant_records(conn, 1)
    validate_records(records, 1)
    count = len([x for x in records["salintel_investigation_items"]
                 if x["investigation_id"] == record_id and "salintel_monitoring_profile" in x["detail"]])
    assert count == 6
    replace_tenant_records(conn, 1, records)
    restored = conn.execute("SELECT COUNT(*) c FROM salintel_investigation_items WHERE investigation_id=?",
                            (record_id,)).fetchone()["c"]
    assert restored >= 6
    conn.close()
    print("SALINTEL_MONITORING_SMOKE_PASS")


if __name__ == "__main__":
    main()
