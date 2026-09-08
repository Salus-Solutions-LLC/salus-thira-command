#!/usr/bin/env python3
"""Acceptance checks for SalCAPA Mission Map and Mission Structure (issue #213)."""
import os
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
    other_tenant = {
        "X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Other Tenant Director", "X-Salus-Clearance": "Highly Sensitive",
    }

    mode = client.get("/api/system/mode").json()
    assert mode["version"] == "3.86", mode
    catalog = client.get("/api/salcapa/mission-map/catalog", headers=director)
    assert catalog.status_code == 200, catalog.text
    catalog = catalog.json()
    assert catalog["name"] == "Mission Map"
    assert catalog["principle"] == "People lead. Methods guide. Technology supports. Evidence proves."
    assert catalog["mission_structure"].startswith("Mission → Priorities → Objectives")
    labels = {route["label"] for route in catalog["routes"]}
    assert "SEE — SalINTEL™" in labels
    assert "DECIDE — SalTHIRA™ and authorized people" in labels
    assert "COORDINATE — SalCAPA™" in labels
    assert "ACT — SalOPS™" in labels
    assert "PROVE — cross-cutting Assurance & Results" in labels
    assert not any(state in {"Red", "Orange", "Amber", "Green"} for state in catalog["workflow_states"])

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

    root = client.get("/")
    assert root.status_code == 200
    html = root.text
    assert 'data-view="mission_map"' in html
    assert '/static/mission-map.css' in html and '/static/mission-map.js' in html
    js = (ROOT / "static" / "mission-map.js").read_text(encoding="utf-8")
    assert "Mission Map" in js and "Conventional list view" in js
    assert "SalCAPA makes" not in js and "SalTHIRA coordinates" not in js
    css = (ROOT / "static" / "mission-map.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    print("SalCAPA Mission Map acceptance checks passed.")


if __name__ == "__main__":
    main()
