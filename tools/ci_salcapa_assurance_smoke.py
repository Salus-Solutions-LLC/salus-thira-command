#!/usr/bin/env python3
"""Acceptance checks for the server-derived SalCAPA PROVE foundation."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "assurance.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime


def main():
    client = TestClient(salcapa_runtime.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "Assurance Director", "X-Salus-Clearance": "Highly Sensitive"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member", "X-Salus-Clearance": "Standard"}
    other = {"X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
             "X-Salus-User": "Other Tenant", "X-Salus-Clearance": "Highly Sensitive"}

    assert client.get("/api/system/mode").json()["version"] == "3.80"
    root = client.get("/")
    assert root.status_code == 200
    for marker in ('data-view="prove"', "/static/salcapa-assurance.css",
                   "/static/salcapa-assurance.js", "/static/salcapa-display.js"):
        assert marker in root.text, marker

    stamp = salcapa_runtime.core.now()
    conn = salcapa_runtime.core.db()
    conn.execute(
        "INSERT INTO intel_findings(tenant_id,assessment_id,title,source,relevance,credibility,"
        "validation_status,operational_significance,status,qualified_by,qualified_at,created_by,"
        "created_at,updated_at) VALUES(1,1,?,'Synthetic governed source','Relevant','High',"
        "'Qualified','Supports synthetic assurance trace','Sent to SalTHIRA',?,?,?, ?,?)",
        ("SYNTHETIC qualified intelligence", "Assurance Director", stamp,
         "Assurance Director", stamp, stamp),
    )
    intel_id = int(conn.execute("SELECT MAX(id) id FROM intel_findings").fetchone()["id"])
    conn.execute(
        "INSERT INTO reassessment_triggers(assessment_id,source,trigger_type,description,severity,"
        "affected_record_type,affected_record_id,status,created_at,updated_at) "
        "VALUES(1,'SalINTEL','Qualified Intelligence','Synthetic explicit trace','High',"
        "'intel_finding',?,'Open',?,?)", (intel_id, stamp, stamp),
    )
    conn.execute(
        "INSERT INTO evidence(assessment_id,capability_id,title,verification_status,"
        "lifecycle_status,sensitivity,created_at,updated_at) "
        "VALUES(1,1,?,'Verified','Current','Standard',?,?)",
        ("SYNTHETIC member-safe evidence", stamp, stamp),
    )
    member_evidence_id = int(conn.execute("SELECT MAX(id) id FROM evidence").fetchone()["id"])
    conn.execute(
        "INSERT INTO decisions(assessment_id,improvement_id,decision_type,authority,rationale,"
        "created_at,updated_at) VALUES(1,1,'Approve','Synthetic Authority',"
        "'Synthetic approval without action for gap testing',?,?)", (stamp, stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_plans(id,tenant_id,assessment_id,title,plan_type,"
        "scope_statement,training_requirements,exercise_validation_requirements,evidence_refs_json,"
        "sensitivity,status,member_adoption_status,created_by,created_at,updated_by,updated_at) "
        "VALUES('synthetic-plan-prove',1,1,'SYNTHETIC released preparedness plan','EOP',"
        "'Synthetic assurance scope','Required training','Required exercise',?,'Standard','Approved','Adopted',?,?,?,?)",
        (f'[\"{member_evidence_id}\"]', "Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_plans(id,tenant_id,assessment_id,title,plan_type,"
        "scope_statement,training_requirements,exercise_validation_requirements,sensitivity,status,"
        "created_by,created_at,updated_by,updated_at) VALUES('synthetic-plan-gap',1,1,"
        "'SYNTHETIC plan with missing handoffs','COOP','Synthetic assurance gap scope',"
        "'Required training','Required exercise','Standard','Approved',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_training(id,tenant_id,assessment_id,plan_id,title,objective,"
        "status,member_release_status,evidence_refs_json,created_by,created_at,updated_by,updated_at) "
        "VALUES('synthetic-training-prove',1,1,'synthetic-plan-prove','SYNTHETIC completed training',"
        "'Demonstrate plan role', 'Completed','Released',?,?,?, ?,?)",
        (f'[\"{member_evidence_id}\"]', "Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_exercises(id,tenant_id,assessment_id,plan_id,title,"
        "exercise_type,scope_statement,sensitivity,status,created_by,created_at,updated_by,updated_at) "
        "VALUES('synthetic-exercise-prove',1,1,'synthetic-plan-prove','SYNTHETIC evaluated exercise',"
        "'Tabletop Exercise','Synthetic validation scope','Standard','Evaluated',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_observations(id,tenant_id,exercise_id,epistemic_state,title,"
        "observation,status,member_release_status,created_by,created_at,updated_by,updated_at) "
        "VALUES('synthetic-observation-prove',1,'synthetic-exercise-prove','Verified Fact',"
        "'SYNTHETIC exercise observation','Observed synthetic result','Open','Released',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_corrective_actions(id,tenant_id,observation_id,exercise_id,"
        "plan_id,assessment_id,title,description,completion_evidence_json,validation_result,status,"
        "member_release_status,created_by,created_at,updated_by,updated_at) VALUES("
        "'synthetic-corrective-prove',1,'synthetic-observation-prove','synthetic-exercise-prove',"
        "'synthetic-plan-prove',1,'SYNTHETIC validated corrective','Synthetic corrective result',"
        "'[\"field-evidence\"]','Validated through synthetic evaluation','Validated','Released',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_aars(id,tenant_id,exercise_id,title,corrective_action_ids_json,"
        "status,created_by,created_at,updated_by,updated_at) VALUES('synthetic-aar-prove',1,"
        "'synthetic-exercise-prove','SYNTHETIC released AAR','[\"synthetic-corrective-prove\"]',"
        "'Released',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.commit()
    conn.close()

    create_path = "/api/salcapa/assurance/assessments/1/packages"
    assert client.post(
        create_path, headers=analyst,
        json={"package_type": "Executive Assurance", "status": "Released"},
    ).status_code == 422
    assert client.post(
        create_path, headers=member, json={"package_type": "Executive Assurance"},
    ).status_code == 403
    created = client.post(
        create_path, headers=analyst, json={"package_type": "Executive Assurance"},
    )
    assert created.status_code == 200, created.text
    package = created.json()
    assert package["status"] == "Draft" and package["package_version"] == 1
    assert package["classification"] == "Standard"
    assert package["server_derived"] is True and package["member_visible"] is False
    assert len(package["snapshot_sha256"]) == 64
    snapshot_path = f"/api/reports/versions/{package['id']}/snapshot"
    assert client.get(snapshot_path, headers=member).status_code == 403
    internal_snapshot = client.get(snapshot_path, headers=analyst)
    assert internal_snapshot.status_code == 200, internal_snapshot.text
    assert internal_snapshot.json()["trace_policy"]["explicit_links_only"] is True
    for status in ("Reviewed", "Approved", "Released"):
        transition = client.post(
            f"/api/reports/versions/{package['id']}/transition", headers=analyst,
            json={"status": status, "reason": f"Synthetic {status} authority basis"},
        )
        assert transition.status_code == 200, transition.text
    released_member = client.get("/api/salcapa/assurance?assessment_id=1", headers=member)
    assert released_member.status_code == 200, released_member.text
    visible_packages = released_member.json()["assessments"][0]["assurance_packages"]
    assert len(visible_packages) == 1 and visible_packages[0]["status"] == "Released"
    assert set(visible_packages[0]) == {
        "id", "assessment_id", "assessment_version", "package_type",
        "package_version", "status", "snapshot_sha256", "classification", "released_at",
    }
    assert client.get(snapshot_path, headers=member).status_code == 200

    conn = salcapa_runtime.core.db()
    conn.execute(
        "INSERT INTO evidence(assessment_id,capability_id,title,verification_status,"
        "lifecycle_status,sensitivity,created_at,updated_at) "
        "VALUES(1,1,?,'Verified','Current','Highly Sensitive',?,?)",
        ("SYNTHETIC restricted evidence", stamp, stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_plans(id,tenant_id,assessment_id,title,plan_type,"
        "scope_statement,sensitivity,status,created_by,created_at,updated_by,updated_at) VALUES("
        "'synthetic-plan-restricted',1,1,'SYNTHETIC restricted plan','EOP','Restricted scope',"
        "'Highly Sensitive','Approved',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.execute(
        "INSERT INTO salops_preparedness_exercises(id,tenant_id,assessment_id,plan_id,title,"
        "exercise_type,scope_statement,sensitivity,status,created_by,created_at,updated_by,updated_at) "
        "VALUES('synthetic-exercise-restricted',1,1,'synthetic-plan-restricted',"
        "'SYNTHETIC restricted exercise','Tabletop Exercise','Restricted exercise scope',"
        "'Highly Sensitive','Approved',?,?,?,?)",
        ("Assurance Director", stamp, "Assurance Director", stamp),
    )
    conn.commit()
    conn.close()
    restricted = client.post(
        create_path, headers=analyst, json={"package_type": "Evidence & Provenance"},
    )
    assert restricted.status_code == 200, restricted.text
    restricted_package = restricted.json()
    assert restricted_package["classification"] == "Highly Sensitive"
    restricted_snapshot_path = f"/api/reports/versions/{restricted_package['id']}/snapshot"
    for status in ("Reviewed", "Approved", "Released"):
        transition = client.post(
            f"/api/reports/versions/{restricted_package['id']}/transition", headers=analyst,
            json={"status": status, "reason": f"Synthetic restricted {status} basis"},
        )
        assert transition.status_code == 200, transition.text
    assert client.get(restricted_snapshot_path, headers=member).status_code == 403

    path = "/api/salcapa/assurance?assessment_id=1"
    response = client.get(path, headers=analyst)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["workspace"] == "PROVE — Assurance & Results"
    assert data["cross_cutting"] is True and data["not_a_separate_product"] is True
    assert data["package_types"] == [
        "Executive Assurance", "Capability Validation",
        "Decision-to-Action Traceability", "Evidence & Provenance",
        "After-Action & Improvement", "Protected Member Results",
    ]
    result = data["assessments"][0]
    assert result["trace_policy"] == {
        "server_derived": True, "explicit_links_only": True,
        "missing_links_are_gaps": True, "automatic_completion": False,
        "automatic_disclosure": False, "automatic_authority": False,
        "preparedness_lifecycles_remain_authoritative": True,
        "training_completion_is_readiness_proof": False,
    }
    stages = {item["key"]: item for item in result["stages"]}
    assert list(stages) == [
        "qualified_intelligence", "risk_priority", "decision", "authorized_action",
        "execution", "evidence", "result_validation", "reassessment",
    ]
    assert stages["qualified_intelligence"]["record_count"] == 1
    assert stages["evidence"]["record_count"] == 8
    assert stages["authorized_action"]["state"] == "Evidence present"
    assert stages["execution"]["record_count"] == 2
    assert stages["result_validation"]["record_count"] == 2
    assert result["preparedness_trace"] == {
        "plans": 3, "training": 1, "exercises": 2, "observations": 1,
        "corrective_actions": 1, "after_action_reports": 1,
    }
    edges = {(item["source"], item["target"]) for item in result["explicit_edges"]}
    assert (f"intel_finding:{intel_id}", "reassessment_trigger:1") in edges
    assert ("threat:1", "scenario:1") in edges
    assert ("scenario:1", "capability:1") in edges
    assert ("capability:1", "gap:1") in edges
    assert ("gap:1", "improvement:1") in edges
    assert ("improvement:1", "decision:1") in edges
    assert (f"evidence:{member_evidence_id}", "preparedness_plan:synthetic-plan-prove") in edges
    assert ("preparedness_plan:synthetic-plan-prove", "preparedness_training:synthetic-training-prove") in edges
    assert ("preparedness_plan:synthetic-plan-prove", "preparedness_exercise:synthetic-exercise-prove") in edges
    assert ("preparedness_exercise:synthetic-exercise-prove", "preparedness_observation:synthetic-observation-prove") in edges
    assert ("preparedness_observation:synthetic-observation-prove", "preparedness_corrective_action:synthetic-corrective-prove") in edges
    assert ("preparedness_exercise:synthetic-exercise-prove", "preparedness_aar:synthetic-aar-prove") in edges
    assert ("preparedness_corrective_action:synthetic-corrective-prove", "preparedness_aar:synthetic-aar-prove") in edges
    gap_keys = {item["gap_key"] for item in result["assurance_gaps"]}
    assert "decision:1:action" in gap_keys
    assert "preparedness_plan:synthetic-plan-gap:training" in gap_keys
    assert "preparedness_plan:synthetic-plan-gap:exercise" in gap_keys
    assert client.post(path, headers=analyst, json={"complete": True}).status_code == 405

    member_response = client.get(path, headers=member)
    assert member_response.status_code == 200, member_response.text
    member_result = member_response.json()["assessments"][0]
    assert member_result["stages"][5]["record_count"] == 6
    assert member_result["preparedness_trace"] == {
        "plans": 2, "training": 1, "exercises": 1, "observations": 1,
        "corrective_actions": 1, "after_action_reports": 1,
    }
    evidence_nodes = [item for item in member_result["nodes"] if item["record_type"] == "evidence"]
    assert [item["label"] for item in evidence_nodes] == ["SYNTHETIC member-safe evidence"]
    assert not any("restricted" in item["label"].lower() for item in member_result["nodes"])
    assert len(member_result["assurance_packages"]) == 1
    assert client.get(path, headers=other).status_code == 403
    print("SALCAPA_ASSURANCE_SMOKE_PASS")


if __name__ == "__main__":
    main()
