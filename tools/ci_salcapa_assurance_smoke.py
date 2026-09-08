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

    assert client.get("/api/system/mode").json()["version"] == "3.66"
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
    conn.execute(
        "INSERT INTO decisions(assessment_id,improvement_id,decision_type,authority,rationale,"
        "created_at,updated_at) VALUES(1,1,'Approve','Synthetic Authority',"
        "'Synthetic approval without action for gap testing',?,?)", (stamp, stamp),
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
    }
    stages = {item["key"]: item for item in result["stages"]}
    assert list(stages) == [
        "qualified_intelligence", "risk_priority", "decision", "authorized_action",
        "execution", "evidence", "result_validation", "reassessment",
    ]
    assert stages["qualified_intelligence"]["record_count"] == 1
    assert stages["evidence"]["record_count"] == 4
    assert stages["authorized_action"]["state"] == "Assurance gap"
    edges = {(item["source"], item["target"]) for item in result["explicit_edges"]}
    assert (f"intel_finding:{intel_id}", "reassessment_trigger:1") in edges
    assert ("threat:1", "scenario:1") in edges
    assert ("scenario:1", "capability:1") in edges
    assert ("capability:1", "gap:1") in edges
    assert ("gap:1", "improvement:1") in edges
    assert ("improvement:1", "decision:1") in edges
    gap_keys = {item["gap_key"] for item in result["assurance_gaps"]}
    assert "decision:1:action" in gap_keys
    assert client.post(path, headers=analyst, json={"complete": True}).status_code == 405

    member_response = client.get(path, headers=member)
    assert member_response.status_code == 200, member_response.text
    member_result = member_response.json()["assessments"][0]
    assert member_result["stages"][5]["record_count"] == 2
    evidence_nodes = [item for item in member_result["nodes"] if item["record_type"] == "evidence"]
    assert [item["label"] for item in evidence_nodes] == ["SYNTHETIC member-safe evidence"]
    assert len(member_result["assurance_packages"]) == 1
    assert client.get(path, headers=other).status_code == 403
    print("SALCAPA_ASSURANCE_SMOKE_PASS")


if __name__ == "__main__":
    main()
