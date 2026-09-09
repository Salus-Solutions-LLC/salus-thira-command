#!/usr/bin/env python3
"""Acceptance checks for SalCAPA Mission Map and Mission Structure (issue #213)."""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "mission-map.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime
from tools.run_current_release_smoke import normalized_source


def post(client, path, headers, payload, expected=200):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == expected, f"{path}: {response.status_code} {response.text}"
    return response


def main():
    client = TestClient(salcapa_runtime.app)
    director = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Mission Map Director", "X-Salus-Clearance": "Highly Sensitive",
    }
    analyst = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Lead Assessor",
        "X-Salus-User": "Mission Map Analyst", "X-Salus-Clearance": "Highly Sensitive",
    }
    member = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Protected Member User", "X-Salus-Clearance": "Standard",
    }
    other_member = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Different Protected Member User", "X-Salus-Clearance": "Standard",
    }
    other_tenant = {
        "X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Other Tenant Director", "X-Salus-Clearance": "Highly Sensitive",
    }

    mode = client.get("/api/system/mode").json()
    assert mode["version"] == "3.92", mode
    adapter_fixture = Path(WORKSPACE.name) / "release-adapter-fixture.py"
    adapter_fixture.write_text(
        'xml = b\'<?xml version="1.0"?>\'\n'
        'assert mode["version"] == "3.91"\n'
        'marker = \'SALCAPA_RELEASE_VERSION = "3.91"\'\n',
        encoding="utf-8",
    )
    adapted, changes = normalized_source(adapter_fixture, "3.92")
    assert 'version="1.0"' in adapted
    assert 'mode["version"] == "3.92"' in adapted
    assert 'SALCAPA_RELEASE_VERSION = "3.92"' in adapted
    # The archived-regression runner may already have normalized this embedded
    # fixture before this smoke exercises the same narrow adapter.
    assert [old for _, old, _ in changes] in ([], ["3.91", "3.91"])
    catalog = client.get("/api/salcapa/mission-map/catalog", headers=director)
    assert catalog.status_code == 200, catalog.text
    catalog = catalog.json()
    assert catalog["name"] == "Mission Map"
    assert catalog["principle"] == "People lead. Methods guide. Technology supports. Evidence proves."
    assert catalog["mission_structure"].startswith("Mission → Priorities → Objectives")
    assert "arrow keys, Home, or End" in catalog["keyboard_guidance"]
    assert "without relying on color" in catalog["accessibility_guidance"]
    labels = {route["label"] for route in catalog["routes"]}
    assert "SEE — SalINTEL™" in labels
    assert "DECIDE — SalTHIRA™ and authorized people" in labels
    assert "COORDINATE — SalCAPA™" in labels
    assert "ACT — SalOPS™" in labels
    assert "PROVE — cross-cutting Assurance & Results" in labels
    assert not any(state in {"Red", "Orange", "Amber", "Green"} for state in catalog["workflow_states"])
    assert "Waiting / input needed" in catalog["attention_states"]
    assert "Decision / coordination needed" in catalog["attention_states"]
    assert "do not change scope" in catalog["filter_guidance"]
    assert catalog["preparedness_overlay_types"] == ["Plan", "Training", "Exercise"]
    assert "read-only projections" in catalog["overlay_guidance"]
    assert "Printing does not approve" in catalog["report_guidance"]

    # No browser-provided map coordinate or arbitrary state can enter the governed model.
    forged_position = dict(
        assessment_id=1, node_type="Mission", title="Continuity mission",
        purpose="Maintain essential functions during disruption.", parent_id=None,
        functional_area="Mission Structure", owner="Mission Executive", authority="Approved charter",
        internal_next_step="Establish objectives.", internal_waiting_on="", member_summary="Mission overview",
        member_next_step="Review current objectives.", member_waiting_on="", member_owner="Member Executive",
        evidence_state="Not Applicable", sensitivity="Standard", map_x=9001,
    )
    response = client.post("/api/salcapa/mission-map/nodes", headers=director, json=forged_position)
    assert response.status_code == 422, response.text

    mission = post(client, "/api/salcapa/mission-map/nodes", director, {
        "assessment_id": 1, "node_type": "Mission", "title": "Maintain essential operations",
        "purpose": "Maintain essential operations and protect people during disruptive events.",
        "parent_id": None, "functional_area": "Mission Structure", "owner": "Executive Sponsor",
        "authority": "Protected Member governance and approved assessment scope.",
        "internal_next_step": "Confirm the capability objectives that support this mission.",
        "internal_waiting_on": "", "member_summary": "Maintain essential operations and protect people.",
        "member_next_step": "Review the objectives and any requested decisions.", "member_waiting_on": "",
        "member_owner": "Executive Sponsor", "evidence_state": "Not Applicable", "sensitivity": "Standard",
    }).json()
    mission_id = mission["id"]
    assert mission["route_key"] == "mission-structure" and mission["station"] == "Mission"

    objective = post(client, "/api/salcapa/mission-map/nodes", director, {
        "assessment_id": 1, "node_type": "Objective", "title": "Demonstrate emergency power capability",
        "purpose": "Demonstrate that essential functions can be supported during an extended utility outage.",
        "parent_id": mission_id, "functional_area": "Mission Structure", "owner": "Facility Lead",
        "authority": "Objective established within the approved continuity mission.",
        "internal_next_step": "Select and authorize the practical approach.", "internal_waiting_on": "",
        "member_summary": "Demonstrate emergency power capability for essential functions.",
        "member_next_step": "Review the selected approach when presented.", "member_waiting_on": "",
        "member_owner": "Facility Lead", "evidence_state": "Evidence Needed", "sensitivity": "Standard",
    }).json()
    assert [entry["node_type"] for entry in objective["mission_path"]] == ["Mission"]

    # Parent rank and exact governed scope are server-enforced.
    bad_parent = client.post("/api/salcapa/mission-map/nodes", headers=director, json={
        "assessment_id": 1, "node_type": "Priority", "title": "Invalid child priority",
        "purpose": "This must fail because an objective cannot parent a priority.",
        "parent_id": objective["id"], "functional_area": "Mission Structure", "owner": "",
        "authority": "", "internal_next_step": "", "internal_waiting_on": "", "member_summary": "",
        "member_next_step": "", "member_waiting_on": "", "member_owner": "",
        "evidence_state": "Not Applicable", "sensitivity": "Standard",
    })
    assert bad_parent.status_code == 409, bad_parent.text
    bad_scope = client.post("/api/salcapa/mission-map/nodes", headers=director, json={
        "assessment_id": None, "node_type": "Strategy", "title": "Invalid cross-scope strategy",
        "purpose": "A tenant-level item cannot attach to a scoped objective.",
        "parent_id": objective["id"], "functional_area": "Mission Structure", "owner": "",
        "authority": "", "internal_next_step": "", "internal_waiting_on": "", "member_summary": "",
        "member_next_step": "", "member_waiting_on": "", "member_owner": "",
        "evidence_state": "Not Applicable", "sensitivity": "Standard",
    })
    assert bad_scope.status_code == 409, bad_scope.text

    task = post(client, "/api/salcapa/mission-map/nodes", director, {
        "assessment_id": 1, "node_type": "Task / Assignment", "title": "Conduct governed generator load test",
        "purpose": "Provide evidence supporting the emergency-power objective.", "parent_id": objective["id"],
        "functional_area": "SalOPS", "owner": "Salus Operations Lead",
        "authority": "Task remains subject to site authorization, safety requirements, and approved operational scope.",
        "internal_next_step": "Coordinate the authorized load test.", "internal_waiting_on": "Site test window",
        "member_summary": "Emergency-power capability validation is being coordinated.",
        "member_next_step": "Confirm the authorized test window and facility point of contact.",
        "member_waiting_on": "Authorized test window", "member_owner": "Facility Point of Contact",
        "evidence_state": "Evidence Needed", "sensitivity": "Standard",
    }).json()
    assert task["route_key"] == "salops" and task["station"] == "Planning"
    assert [entry["node_type"] for entry in task["mission_path"]] == ["Mission", "Objective"]

    # Visual location changes only after governed state transition; arbitrary jumps need documented authority.
    planned = post(client, f"/api/salcapa/mission-map/nodes/{task['id']}/transition", analyst, {
        "status": "Planned", "reason": "Planning record completed within the approved scope.",
        "internal_next_step": "Await authorization before assignment.", "internal_waiting_on": "Authorization",
        "member_next_step": None, "member_waiting_on": None,
    }).json()
    assert planned["station"] == "Planning"
    analyst_jump = client.post(f"/api/salcapa/mission-map/nodes/{task['id']}/transition", headers=analyst, json={
        "status": "In Progress", "reason": "Attempt unapproved state jump.", "internal_next_step": None,
        "internal_waiting_on": None, "member_next_step": None, "member_waiting_on": None,
    })
    assert analyst_jump.status_code == 409, analyst_jump.text
    active = post(client, f"/api/salcapa/mission-map/nodes/{task['id']}/transition", director, {
        "status": "In Progress", "reason": "Assessment Director records the authorized operational start.",
        "internal_next_step": "Complete the authorized test and preserve evidence.", "internal_waiting_on": "",
        "member_next_step": None, "member_waiting_on": None,
    }).json()
    assert active["station"] == "In Progress"

    # Evidence/result objects are cross-cutting PROVE records; other placement fails closed.
    bad_evidence_area = client.post("/api/salcapa/mission-map/nodes", headers=director, json={
        "assessment_id": 1, "node_type": "Evidence & Result", "title": "Invalid evidence placement",
        "purpose": "Must fail outside PROVE.", "parent_id": task["id"], "functional_area": "SalOPS",
        "owner": "", "authority": "", "internal_next_step": "", "internal_waiting_on": "",
        "member_summary": "", "member_next_step": "", "member_waiting_on": "", "member_owner": "",
        "evidence_state": "Evidence Needed", "sensitivity": "Standard",
    })
    assert bad_evidence_area.status_code == 422, bad_evidence_area.text
    evidence = post(client, "/api/salcapa/mission-map/nodes", director, {
        "assessment_id": 1, "node_type": "Evidence & Result", "title": "Generator validation evidence",
        "purpose": "Preserve evidence and result interpretation supporting the objective.", "parent_id": task["id"],
        "functional_area": "PROVE", "owner": "Salus Reviewer",
        "authority": "Evidence requires human qualification and validation before a demonstrated state is recorded.",
        "internal_next_step": "Review source evidence.", "internal_waiting_on": "Test record",
        "member_summary": "Evidence is being assembled to validate emergency-power capability.",
        "member_next_step": "No action is required unless Salus requests supporting records.",
        "member_waiting_on": "", "member_owner": "Salus Reviewer",
        "evidence_state": "Evidence Needed", "sensitivity": "Standard",
    }).json()
    assert evidence["route_key"] == "prove" and evidence["station"] == "Evidence Needed"
    no_result = client.post(f"/api/salcapa/mission-map/nodes/{evidence['id']}/evidence-state", headers=director, json={
        "evidence_state": "Demonstrated", "result_summary": "", "reason": "Must fail without result basis."
    })
    assert no_result.status_code == 422, no_result.text
    demonstrated = post(client, f"/api/salcapa/mission-map/nodes/{evidence['id']}/evidence-state", director, {
        "evidence_state": "Demonstrated",
        "result_summary": "Reviewed test evidence demonstrates the recorded capability within the approved test scope.",
        "reason": "Assessment Director records the human validation judgment from reviewed evidence.",
    }).json()
    assert demonstrated["evidence_state"] == "Demonstrated"

    linked = post(client, "/api/salcapa/mission-map/links", director, {
        "source_node_id": evidence["id"], "target_node_id": objective["id"],
        "relationship": "Produces Evidence For",
        "basis": "The governed validation evidence supports the stated emergency-power objective.",
    }).json()
    assert linked["relationship"] == "Produces Evidence For"
    self_link = client.post("/api/salcapa/mission-map/links", headers=director, json={
        "source_node_id": task["id"], "target_node_id": task["id"], "relationship": "Related To",
        "basis": "Self-links are not meaningful."
    })
    assert self_link.status_code == 409, self_link.text

    # Protected Members cannot see internal work until explicitly released.
    before = client.get("/api/salcapa/mission-map?assessment_id=1", headers=member)
    assert before.status_code == 200, before.text
    assert before.json()["items"] == []
    assert before.json()["fallback"]["available"] is True
    assert client.post(f"/api/salcapa/mission-map/nodes/{mission_id}/release", headers=member,
                       json={"reason": "Member cannot self-release."}).status_code == 403

    post(client, f"/api/salcapa/mission-map/nodes/{mission_id}/release", director,
         {"reason": "Release the approved mission orientation to the Protected Member."})
    post(client, f"/api/salcapa/mission-map/nodes/{objective['id']}/release", director,
         {"reason": "Release the approved objective orientation to the Protected Member."})
    post(client, f"/api/salcapa/mission-map/nodes/{task['id']}/release", director,
         {"reason": "Release the member-safe task status and requested next step."})
    post(client, f"/api/salcapa/mission-map/nodes/{evidence['id']}/release", director,
         {"reason": "Release the member-safe validation status."})

    member_map = client.get("/api/salcapa/mission-map?assessment_id=1", headers=member)
    assert member_map.status_code == 200, member_map.text
    member_map = member_map.json()
    assert len(member_map["items"]) == 4
    member_task = next(item for item in member_map["items"] if item["id"] == task["id"])
    assert member_task["purpose"] == "Emergency-power capability validation is being coordinated."
    assert member_task["owner"] == "Facility Point of Contact"
    assert member_task["waiting_on"] == "Authorized test window"
    assert "authority" not in member_task and "sensitivity" not in member_task and "visibility" not in member_task
    assert "Salus Operations Lead" not in str(member_task)
    assert "site authorization" not in str(member_task).lower()
    assert member_task["mission_path"] == [
        {"id": mission_id, "node_type": "Mission", "title": "Maintain essential operations"},
        {"id": objective["id"], "node_type": "Objective", "title": "Demonstrate emergency power capability"},
    ]

    # Other tenant cannot enumerate or fetch tenant-one Mission Map history.
    other = client.get("/api/salcapa/mission-map", headers=other_tenant)
    assert other.status_code == 200 and all(item["id"] != task["id"] for item in other.json()["items"])
    assert client.get(f"/api/salcapa/mission-map/nodes/{task['id']}/history", headers=other_tenant).status_code == 404

    salus_map = client.get("/api/salcapa/mission-map?assessment_id=1", headers=director)
    assert salus_map.status_code == 200, salus_map.text
    salus_map = salus_map.json()
    salus_task = next(item for item in salus_map["items"] if item["id"] == task["id"])
    assert salus_task["owner"] == "Salus Operations Lead"
    assert salus_task["authority"].startswith("Task remains subject")
    assert salus_map["fallback"]["available"] is True
    assert any(link["relationship"] == "Produces Evidence For" for link in salus_map["links"])
    assert salus_map["portfolio"]["total_items"] == 4
    assert salus_map["portfolio"]["by_route"]["mission-structure"] == 2
    assert salus_map["portfolio"]["by_route"]["salops"] == 1
    assert salus_map["portfolio"]["by_route"]["prove"] == 1
    assert sum(salus_map["portfolio"]["by_age_band"].values()) == 4
    assert all(item["age_days"] >= 0 for item in salus_map["items"])
    assert all(item["age_band"] in {"0–7 days", "8–30 days", "31+ days"} for item in salus_map["items"])
    assert "not scores or judgments about people" in salus_map["portfolio"]["interpretation"]

    filtered = client.get(
        "/api/salcapa/mission-map?assessment_id=1&functional_area=SalOPS&workflow_status=In%20Progress&owner=Salus%20Operations",
        headers=director,
    )
    assert filtered.status_code == 200, filtered.text
    filtered = filtered.json()
    assert [item["id"] for item in filtered["items"]] == [task["id"]]
    assert filtered["portfolio"]["total_items"] == 1
    assert filtered["active_filters"]["functional_area"] == "SalOPS"
    assert filtered["active_filters"]["workflow_status"] == "In Progress"

    waiting = client.get(
        "/api/salcapa/mission-map?assessment_id=1&functional_area=PROVE&attention=Waiting%20%2F%20input%20needed",
        headers=director,
    )
    assert waiting.status_code == 200, waiting.text
    assert [item["id"] for item in waiting.json()["items"]] == [evidence["id"]]
    assert waiting.json()["portfolio"]["by_attention"] == {"Waiting / input needed": 1}

    # Filtering is applied to each role-safe projection; internal owner names cannot be inferred by a member.
    member_internal_owner = client.get(
        "/api/salcapa/mission-map?assessment_id=1&owner=Salus%20Operations", headers=member
    )
    assert member_internal_owner.status_code == 200, member_internal_owner.text
    assert member_internal_owner.json()["items"] == []
    assert member_internal_owner.json()["portfolio"]["total_items"] == 0

    # Existing SalOPS plans, training, and exercises are projected without creating duplicate work records.
    plan = post(client, "/api/salops/preparedness/plans", director, {
        "assessment_id": 1, "title": "Continuity plan", "plan_type": "Emergency Operations Plan",
        "purpose": "Guide coordinated continuity actions during an extended utility outage.",
        "scope_statement": "Essential operations within the authorized assessment scope.",
        "owner": "Salus Planning Lead", "approver": "Protected Member Executive",
    }).json()
    training = post(client, "/api/salops/preparedness/training", director, {
        "assessment_id": 1, "plan_id": plan["id"], "title": "Continuity roles workshop",
        "objective": "Prepare assigned personnel to carry out the approved continuity plan.",
        "audience": "Continuity team", "delivery_type": "Workshop", "instructor": "Salus Training Lead",
        "scheduled_at": "2026-09-20T14:00:00Z",
    }).json()
    exercise = post(client, "/api/salops/preparedness/exercises", director, {
        "assessment_id": 1, "plan_id": plan["id"], "title": "Utility outage tabletop exercise",
        "exercise_type": "Tabletop Exercise", "purpose": "Examine the approved continuity plan.",
        "scope_statement": "Authorized continuity team and essential operations.",
        "scheduled_at": "2026-09-25T15:00:00Z", "sensitivity": "Standard",
    }).json()

    internal_overlays = client.get(
        "/api/salcapa/mission-map?assessment_id=1&functional_area=SalOPS", headers=director
    )
    assert internal_overlays.status_code == 200, internal_overlays.text
    internal_overlays = [item for item in internal_overlays.json()["items"] if item.get("read_only")]
    assert {item["id"] for item in internal_overlays} == {
        f"salops-plan:{plan['id']}", f"salops-training:{training['id']}", f"salops-exercise:{exercise['id']}"
    }
    assert {item["source_type"] for item in internal_overlays} == {"Plan", "Training", "Exercise"}
    assert all(item["projection_kind"] == "Preparedness overlay" for item in internal_overlays)
    assert all(item["functional_area"] == "SalOPS" for item in internal_overlays)
    assert all("Change status" in item["projection_basis"] for item in internal_overlays)
    assert next(item for item in internal_overlays if item["source_type"] == "Plan")["owner"] == "Salus Planning Lead"
    assert next(item for item in internal_overlays if item["source_type"] == "Training")["owner"] == "Salus Training Lead"
    assert next(item for item in internal_overlays if item["source_type"] == "Exercise")["owner"] == ""

    # Source disclosure gates—not Mission Map—control Protected Member visibility.
    member_before_sources = client.get("/api/salcapa/mission-map?assessment_id=1", headers=member).json()
    assert not any(item.get("read_only") for item in member_before_sources["items"])
    post(client, f"/api/salops/preparedness/plans/{plan['id']}/transition", analyst,
         {"status": "Reviewed", "reason": "Planning review completed within the authorized scope."})
    post(client, f"/api/salops/preparedness/plans/{plan['id']}/transition", director,
         {"status": "Approved", "reason": "Authorized approver records plan approval for member use."})
    post(client, f"/api/salops/preparedness/training/{training['id']}/release", director,
         {"approved_for_member": True, "reason": "Release the governed training record to the Protected Member."})
    post(client, f"/api/salops/preparedness/exercises/{exercise['id']}/transition", analyst,
         {"status": "Reviewed", "reason": "Exercise design review completed."})
    post(client, f"/api/salops/preparedness/exercises/{exercise['id']}/transition", director,
         {"status": "Approved", "reason": "Authorized approver records exercise approval."})

    member_sources = client.get("/api/salcapa/mission-map?assessment_id=1", headers=member)
    assert member_sources.status_code == 200, member_sources.text
    member_overlays = [item for item in member_sources.json()["items"] if item.get("read_only")]
    member_report = member_sources.json()["report"]
    assert member_report["release_version"] == "3.92"
    assert member_report["audience"] == "Protected Member authorized view"
    assert member_report["included_item_count"] == len(member_sources.json()["items"])
    assert member_report["prepared_at_display"].endswith(" UTC")
    assert re.fullmatch(r"\d{2} [A-Z][a-z]+ \d{4} \d{2}:\d{2} UTC", member_report["prepared_at_display"])
    assert "Only released records" in member_report["authorization_basis"]
    assert "does not approve, release, validate" in member_report["governance"]
    assert "Return to SalCAPA" in member_report["correction_and_lifecycle"]
    assert "tenant" not in member_report["scope"].lower()
    assert {item["source_type"] for item in member_overlays} == {"Plan", "Training", "Exercise"}
    member_plan_overlay = next(item for item in member_overlays if item["source_type"] == "Plan")
    member_training = next(item for item in member_overlays if item["source_type"] == "Training")
    member_exercise = next(item for item in member_overlays if item["source_type"] == "Exercise")
    assert (member_plan_overlay["source_status"], member_plan_overlay["status"]) == ("Approved", "Authorized")
    assert (member_training["source_status"], member_training["status"]) == ("Scheduled", "Planned")
    assert (member_exercise["source_status"], member_exercise["status"]) == ("Approved", "Authorized")
    assert member_training["evidence_state"] == "Evidence Needed"
    assert all("authority" not in item and "sensitivity" not in item and "visibility" not in item for item in member_overlays)
    assert "Salus Planning Lead" in str(member_overlays)
    assert "Protected Member Executive" not in str(member_overlays)
    assert member_training["mission_path"] == [
        {"id": f"salops-plan:{plan['id']}", "node_type": "Plan", "title": "Continuity plan"}
    ]

    # Overlay identifiers cannot enter Mission Structure write or transition routes.
    overlay_id = f"salops-plan:{plan['id']}"
    cannot_transition_overlay = client.post(
        f"/api/salcapa/mission-map/nodes/{overlay_id}/transition", headers=director,
        json={"status": "Planned", "reason": "Attempt to change a projection.",
              "internal_next_step": None, "internal_waiting_on": None,
              "member_next_step": None, "member_waiting_on": None},
    )
    assert cannot_transition_overlay.status_code == 404, cannot_transition_overlay.text
    filtered_overlay = client.get(
        "/api/salcapa/mission-map?assessment_id=1&functional_area=SalOPS&workflow_status=Authorized&owner=Salus%20Planning",
        headers=director,
    )
    assert [item["id"] for item in filtered_overlay.json()["items"]] == [overlay_id]

    # Ongoing Monitoring is a tenant-level SalINTEL overlay; profile and outcome authority remain in source records.
    investigation = post(client, "/api/salintel/investigations", director, {
        "domain_key": "organizations", "title": "Essential supplier review",
        "subject_reference": "SUPPLIER-WATCH-001",
        "purpose": "Understand material changes affecting an essential supplier.",
        "requested_tier": 1, "sensitivity": "Standard",
    }).json()
    conn = salcapa_runtime.core.db()
    conn.execute(
        "UPDATE salintel_investigations SET status='Tier Complete',qualification_status='Qualified',"
        "authorized_tier=1,completed_tier=1,disclosure_status='Approved for Tenant' WHERE id=?",
        (investigation["id"],),
    )
    conn.commit(); conn.close()
    requested = post(
        client, f"/api/salintel/investigations/{investigation['id']}/monitoring-selection", member,
        {"recurring_monitoring": "Yes", "purpose": "Maintain an authorized review of relevant supplier changes.",
         "requested_scope": "Documented supplier ownership, service, and continuity changes.",
         "requested_cadence": "Monthly", "requested_start_date": "2026-09-08"},
    ).json()
    profile_key = requested["profile_key"]
    profile_id = f"salintel-monitoring:{investigation['id']}:{profile_key}"
    pending_profile = client.get("/api/salcapa/mission-map?functional_area=SalINTEL", headers=member).json()
    pending_profile = next(item for item in pending_profile["items"] if item["id"] == profile_id)
    assert pending_profile["status"] == "Awaiting Approval"
    assert pending_profile["owner"] == "Authorized Salus reviewer"
    assert "approved_by" not in pending_profile and "lifecycle_reason" not in pending_profile
    assert not any(
        item.get("projection_kind") == "Ongoing monitoring overlay"
        for item in client.get("/api/salcapa/mission-map?functional_area=SalINTEL", headers=other_member).json()["items"]
    )
    assert not any(
        item.get("projection_kind") == "Ongoing monitoring overlay"
        for item in client.get("/api/salcapa/mission-map?assessment_id=1&functional_area=SalINTEL", headers=director).json()["items"]
    )

    approval = {
        "approved_scope": "Bounded review of documented supplier ownership, service, and continuity changes.",
        "cadence": "Monthly", "start_date": "2020-09-08",
        "approved_sources": ["lawful public sources"],
        "change_thresholds": "Verified change affecting ownership, service, or continuity.",
        "escalation_criteria": "Credible material effect on a Protected Member dependency.",
        "review_requirements": "Authorized Salus human review of every recorded cycle outcome.",
        "member_notification_policy": "Separate Salus release decision before any member notice.",
        "member_release_permitted": False, "global_partner_eligible": False,
        "commercial_treatment": "Included",
        "approval_reason": "Approve the bounded monitoring scope and monthly cadence.",
    }
    post(client, f"/api/salintel/investigations/{investigation['id']}/monitoring/{profile_key}/approve",
         director, approval)
    active_profile = client.get("/api/salcapa/mission-map?functional_area=SalINTEL", headers=member).json()
    active_profile = next(item for item in active_profile["items"] if item["id"] == profile_id)
    assert (active_profile["source_status"], active_profile["status"]) == ("Active", "In Progress")
    assert active_profile["cadence"] == "Monthly"
    assert active_profile["attention"] == "Ownership / next step needed"

    material = client.post("/api/materials/upload", headers=director, data={
        "title": "Essential supplier continuity source", "material_kind": "Document",
        "source_origin": "Authorized demonstration public record", "sensitivity": "Standard",
        "purpose_tags": json.dumps(["SalINTEL", "Recurring Monitoring", "lawful public sources"]),
    }, files={"file": ("supplier-source.txt", b"ESSENTIAL SUPPLIER CONTINUITY SOURCE\n", "text/plain")})
    assert material.status_code == 200, material.text
    material_id = material.json()["id"]
    for state, reason in (("Processing", "Begin governed processing."),
                          ("Ready for Human Review", "Source prepared for human review.")):
        response = client.post(f"/api/materials/{material_id}/transition", headers=director,
                               json={"status": state, "reason": reason})
        assert response.status_code == 200, response.text
    linked = client.post(f"/api/materials/{material_id}/links", headers=director, json={
        "target_type": "salintel_investigation", "target_id": investigation["id"],
        "purpose": "Governed monitoring source reuse by reference.",
    })
    assert linked.status_code == 200, linked.text
    cycle_path = f"/api/salintel/investigations/{investigation['id']}/monitoring/{profile_key}/cycles"
    cycle = post(client, cycle_path, director, {"reason": "Conduct the approved monitoring review."}).json()
    outcome = post(client, f"{cycle_path}/{cycle['id']}/outcome", director, {
        "outcome": "Material Change", "narrative": "A source-grounded change requires Salus qualification.",
        "findings": [{"statement": "The reported supplier change requires human review.",
                      "epistemic_state": "Reported Information", "material_ids": [material_id]}],
        "evidence_material_ids": [material_id],
    }).json()
    outcome_id = f"salintel-monitoring-outcome:{investigation['id']}:{outcome['id']}"
    internal_pending = client.get("/api/salcapa/mission-map?functional_area=SalINTEL", headers=director).json()
    internal_pending = next(item for item in internal_pending["items"] if item["id"] == outcome_id)
    assert internal_pending["status"] == "Awaiting Review"
    assert internal_pending["evidence_state"] == "Awaiting Validation"
    assert "not a final finding or decision" in internal_pending["result_summary"]
    assert not any(
        item["id"] == outcome_id
        for item in client.get("/api/salcapa/mission-map?functional_area=SalINTEL", headers=member).json()["items"]
    )
    post(client,
         f"/api/salintel/investigations/{investigation['id']}/monitoring/{profile_key}/outcomes/{outcome['id']}/review",
         director, {"decision": "Qualified", "reason": "Salus reviewer qualified the source basis and distinctions."})
    decision_view = client.get(
        "/api/salcapa/mission-map?functional_area=SalINTEL&attention=Decision%20%2F%20coordination%20needed",
        headers=director,
    ).json()
    qualified = next(item for item in decision_view["items"] if item["id"] == outcome_id)
    assert decision_view["report"]["audience"] == "Salus internal authorized view"
    assert decision_view["report"]["active_filters"]["attention"] == "Decision / coordination needed"
    assert decision_view["report"]["included_item_count"] == len(decision_view["items"])
    assert qualified["status"] == "Completed" and qualified["source_status"] == "Qualified"
    assert qualified["reported_outcome"] == "Material Change"
    assert qualified["attention"] == "Decision / coordination needed"
    assert "does not itself authorize disclosure" in qualified["result_summary"]
    assert client.post(
        f"/api/salcapa/mission-map/nodes/{outcome_id}/transition", headers=director,
        json={"status": "Closed", "reason": "Attempt to change an overlay.",
              "internal_next_step": None, "internal_waiting_on": None,
              "member_next_step": None, "member_waiting_on": None},
    ).status_code == 404
    assert client.get(
        "/api/salcapa/mission-map?workflow_status=Red", headers=director
    ).status_code == 422

    root = client.get("/")
    assert root.status_code == 200
    html = root.text
    assert 'data-view="mission_map"' in html
    assert '/static/mission-map.css' in html and '/static/mission-map.js' in html
    js = (ROOT / "static" / "mission-map.js").read_text(encoding="utf-8")
    assert "Mission Map" in js and "Conventional list view" in js
    assert "Authorized portfolio view" in js and "Apply filters" in js
    assert "Prepare printable view" in js and "missionMapPrintableReport" in js
    assert "window.print()" in js and "afterprint" in js
    assert "Printing preserves this authorized view" in js
    assert "missionMapMarkerKey" in js and "ArrowRight" in js and "Home" in js and "End" in js
    assert "prefers-reduced-motion: reduce" in js and "behavior:missionMapReducedMotion()?'auto':'smooth'" in js
    assert 'role="status"' in js and 'aria-live="polite"' in js and 'aria-controls="mission-map-detail"' in js
    assert 'aria-labelledby="mission-map-heading"' in js and 'aria-describedby="mission-print-guidance"' in js
    assert "missionMapAnnounce" in js and "missionMapRestoreFocus" in js
    assert "missionMapOpenFallback" in js and "fallback.open=true" in js
    assert "Authoritative source" in js and "!item.read_only" in js
    assert "Waiting / input needed" in js and "not scores or judgments about people" not in js
    assert "SalCAPA makes" not in js and "SalTHIRA coordinates" not in js
    css = (ROOT / "static" / "mission-map.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert "forced-colors:active" in css and ".mission-skip-link:focus" in css
    assert ".mission-marker:focus-visible" in css and "min-height:2.75rem" in css
    assert "animation-duration:.01ms!important" in css and "scroll-behavior:auto!important" in css
    assert ".mission-filter-grid" in css and ".mission-portfolio-grid" in css
    assert "@media print" in css and ".mission-print-version" in css
    assert "word-break:normal" in css and "body.mission-map-printing" in css
    print("SalCAPA Mission Map acceptance checks passed.")


if __name__ == "__main__":
    main()
