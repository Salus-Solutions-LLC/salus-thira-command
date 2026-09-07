#!/usr/bin/env python3
"""Acceptance checks for governed autonomous emergency-plan assembly."""
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "plan-assembly.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import salcapa_runtime


def main() -> None:
    client = TestClient(salcapa_runtime.app)
    director = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Preparedness Director", "X-Salus-Clearance": "Highly Sensitive",
    }
    member = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Protected Member", "X-Salus-Clearance": "Standard",
    }
    other = {
        "X-Salus-Tenant": "2", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Other Tenant", "X-Salus-Clearance": "Highly Sensitive",
    }

    assert client.get("/api/system/mode").json()["version"] == "3.64"
    catalog_path = "/api/salops/preparedness/plan-assembly/catalog"
    assert client.get(catalog_path, headers=member).status_code == 403
    catalog = client.get(catalog_path, headers=director)
    assert catalog.status_code == 200, catalog.text
    authority = catalog.json()["authority"]
    assert authority["chat_may"] == ["Inspect", "Research", "Reconcile", "Draft", "Compare", "Recommend"]
    assert authority["automatic_release"] is False
    assert authority["automatic_plan_replacement"] is False
    assert authority["automatic_charge"] is False

    plan = client.post("/api/salops/preparedness/plans", headers=director, json={
        "title": "SYNTHETIC Emergency Operations Plan",
        "plan_type": "Emergency Operations",
        "purpose": "Provide a governed synthetic baseline for plan-revision testing.",
        "scope_statement": "SYNTHETIC facility and its documented essential functions.",
        "mission_lenses": ["Prevention", "Protection", "Mitigation", "Response", "Recovery"],
        "sensitivity": "Standard",
    })
    assert plan.status_code == 200, plan.text
    plan_id = plan.json()["id"]
    for status in ("Reviewed", "Approved"):
        response = client.post(
            f"/api/salops/preparedness/plans/{plan_id}/transition", headers=director,
            json={"status": status, "reason": f"SYNTHETIC {status} governance basis."},
        )
        assert response.status_code == 200, response.text
    approved = client.get(f"/api/salops/preparedness/plans/{plan_id}", headers=director).json()["plan"]
    assert approved["status"] == "Approved" and approved["version"] == 1

    create_path = "/api/salops/preparedness/plan-assembly"
    forged = client.post(create_path, headers=director, json={
        "base_plan_id": plan_id, "plan_title": "Forged", "plan_type": "EOP",
        "purpose": "Attempt to forge lifecycle state.", "scope_statement": "Bounded scope.",
        "research_questions": ["What changed?"], "status": "Qualified",
        "qualified_by": "Client", "approved_plan_preserved": False,
    })
    assert forged.status_code == 422
    incomplete = client.post(create_path, headers=director, json={
        "plan_title": "No research plan", "plan_type": "EOP",
        "purpose": "Missing source plan.", "scope_statement": "Bounded scope.",
    })
    assert incomplete.status_code == 422

    created = client.post(create_path, headers=director, json={
        "base_plan_id": plan_id,
        "plan_title": "SYNTHETIC Emergency Operations Plan — proposed revision",
        "plan_type": "Emergency Operations",
        "purpose": "Research whether current capability and authority changes affect the approved plan.",
        "scope_statement": "The exact approved synthetic facility scope; no newly added entity enters automatically.",
        "portfolio_scope": {"facility_refs": ["SYNTHETIC-FACILITY-001"]},
        "internal_record_refs": ["SalINTEL:SYNTHETIC-CHANGE-001", "SalTHIRA:1"],
        "library_refs": ["SALUS-LIB:EOP-STRUCTURE-V1"],
        "authorized_external_sources": ["Authoritative public emergency-management guidance"],
        "source_exclusions": ["Unapproved personal information", "Unapproved partner databases"],
        "research_questions": ["Did the communications dependency materially change?"],
        "known_unknowns": ["Current alternate communications endurance"],
        "assumptions_to_validate": ["Primary notification path remains available during an outage"],
        "sensitivity": "Standard",
    })
    assert created.status_code == 200, created.text
    run = created.json()
    run_id = run["id"]
    assert run["assembly_mode"] == "Revision"
    assert run["status"] == "Research Planning"
    assert run["base_plan_version"] == 1 and len(run["base_plan_sha256"]) == 64
    assert not {"commercial_treatment", "release_status", "approved_by"} & set(run)
    assert client.get(f"{create_path}/{run_id}", headers=member).status_code == 403
    assert client.get(f"{create_path}/{run_id}", headers=other).status_code == 404

    upload = client.post(
        "/api/materials/upload", headers=director,
        files={"file": ("synthetic-guidance.txt", b"SYNTHETIC current authority guidance and communications dependency evidence", "text/plain")},
        data={
            "title": "SYNTHETIC authoritative research capture",
            "material_kind": "Web Capture", "source_origin": "Authorized external research",
            "source_locator": "https://example.invalid/synthetic-authority-guidance",
            "sensitivity": "Standard", "purpose_tags": '["planning","synthetic"]',
            "description": "Synthetic governed source for plan-assembly acceptance.",
            "recording_authority_basis": "Synthetic test authorization.",
        },
    )
    assert upload.status_code == 200, upload.text
    material_id = upload.json()["id"]

    accessed_path = f"{create_path}/{run_id}/sources"
    missing_material = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/source", "citation": "Synthetic source",
        "source_summary": "Synthetic summary without governed material.",
    })
    assert missing_material.status_code == 422
    unavailable_facts = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Unavailable",
        "unavailable_reason": "Source was unavailable in this synthetic run.",
        "source_derived_statements": [{"state": "Reported Information", "statement": "Forged fact"}],
    })
    assert unavailable_facts.status_code == 422
    automated_verified = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/source", "citation": "Synthetic source",
        "governed_material_id": material_id, "source_summary": "Synthetic source summary.",
        "source_derived_statements": [{"state": "Verified Fact", "statement": "Client-forged verification"}],
    })
    assert automated_verified.status_code == 422

    accessed = client.post(accessed_path, headers=director, json={
        "source_kind": "External Research", "access_status": "Accessed",
        "locator": "https://example.invalid/synthetic-authority-guidance",
        "citation": "SYNTHETIC authority guidance, accessed for governed acceptance",
        "governed_material_id": material_id,
        "search_or_collection_method": "Authorized source retrieval and governed capture",
        "source_summary": "The synthetic source reports a changed external communications dependency.",
        "source_derived_statements": [{
            "state": "Reported Information",
            "statement": "The external communications dependency changed after plan approval.",
        }],
        "reliability": "Authoritative synthetic source", "confidence": "High",
    })
    assert accessed.status_code == 200, accessed.text
    source_id = accessed.json()["id"]
    assert accessed.json()["accessed_at"]
    unavailable = client.post(accessed_path, headers=director, json={
        "source_kind": "Approved Partner Return", "access_status": "Partner Needed",
        "unavailable_reason": "No external transmission or partner cost was authorized.",
        "search_or_collection_method": "Partner need identified; no contact initiated.",
    })
    assert unavailable.status_code == 200, unavailable.text
    assert unavailable.json()["accessed_at"] == ""
    assert unavailable.json()["source_derived_statements"] == []

    question = client.post(f"{create_path}/{run_id}/questions", headers=director, json={
        "target_type": "Protected Member",
        "question": "What alternate communications capability is currently approved and available?",
        "purpose": "Resolve the unsupported continuity assumption without inventing client policy.",
        "requested_method": "Document request and authorized interview",
        "related_section_keys": ["communications", "continuity"], "priority": "High",
    })
    assert question.status_code == 200, question.text
    question_id = question.json()["id"]
    assert question.json()["status"] == "Open"
    answer = client.post(f"{create_path}/{run_id}/questions/{question_id}/answer", headers=director, json={
        "response_summary": "Protected Member reports an alternate system; operational validation remains required.",
        "response_source_ref": f"material:{material_id}",
    })
    assert answer.status_code == 200, answer.text
    assert answer.json()["status"] == "Answered"

    for status in ("Collecting", "Drafting"):
        advanced = client.post(f"{create_path}/{run_id}/advance", headers=director, json={
            "status": status, "reason": f"SYNTHETIC gate to {status}; source distinctions preserved.",
        })
        assert advanced.status_code == 200, advanced.text

    unknown_source = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Unsupported reference must fail.", "source_refs": ["pas_missing"],
    })
    assert unknown_source.status_code == 422
    forged_section_fact = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Automated draft cannot create a verified fact.", "source_refs": [source_id],
        "epistemic_items": [{"state": "Verified Fact", "statement": "Forged", "source_refs": [source_id]}],
    })
    assert forged_section_fact.status_code == 422
    section = client.post(f"{create_path}/{run_id}/sections", headers=director, json={
        "section_key": "communications", "title": "Emergency Communications",
        "content": "Use the approved primary notification path. The alternate path requires human authority and validation before adoption.",
        "source_refs": [source_id],
        "epistemic_items": [
            {"state": "Reported Information", "statement": "The external dependency changed.", "source_refs": [source_id]},
            {"state": "Assumption", "statement": "The proposed alternate may support essential notification.", "source_refs": [source_id]},
        ],
        "unsupported_assumptions": ["Alternate-system endurance has not been validated."],
        "known_unknowns": ["Member authority for activation remains unresolved."],
        "dependencies": ["Primary and alternate communications providers"],
        "alternate_capabilities": ["Proposed alternate system; pending human approval"],
        "capability_gaps": ["No validated communications-loss exercise"],
        "change_rationale": "Current source conflicts with the approved plan dependency assumption.",
        "human_authority_required": True,
    })
    assert section.status_code == 200, section.text
    assert section.json()["support_status"] == "Needs Human Authority"
    assert section.json()["section_version"] == 1

    submit = client.post(f"{create_path}/{run_id}/submit", headers=director, json={
        "completion_statement": "Bounded synthetic first-draft revision completed for human review; unresolved authority and validation needs remain explicit.",
        "contradictions": ["Approved plan assumes an unchanged external communications dependency."],
        "missing_authorities": ["Protected Member activation authority for alternate communications."],
        "unresolved_dependencies": ["Alternate provider endurance and restoration priority."],
        "affected_sections": ["communications", "continuity"],
        "proposed_training_actions": ["Train designated communications alternates after approval."],
        "proposed_exercise_actions": ["Conduct a communications-loss drill."],
        "proposed_validation_actions": ["Validate endurance and restoration assumptions."],
        "change_rationale": "Actually accessed governed source indicates a material dependency change.",
    })
    assert submit.status_code == 200, submit.text
    assert submit.json()["status"] == "Submitted for Human Review"
    assert len(submit.json()["content_sha256"]) == 64
    premature = client.post(f"{create_path}/{run_id}/revision-recommendations", headers=director, json={
        "material_change_summary": "Premature", "recommendation": "Must fail before qualification.",
    })
    assert premature.status_code == 409

    review = client.post(f"{create_path}/{run_id}/review", headers=director, json={
        "decision": "Human Reviewed",
        "reason": "Salus reviewer challenged sources, assumptions, authority gaps, and proposed validation actions.",
    })
    assert review.status_code == 200, review.text
    qualify = client.post(f"{create_path}/{run_id}/qualify", headers=director, json={
        "reason": "Human-qualified as a bounded planning product and revision recommendation basis; not approved or released.",
    })
    assert qualify.status_code == 200, qualify.text
    assert qualify.json()["status"] == "Qualified"

    recommendation = client.post(f"{create_path}/{run_id}/revision-recommendations", headers=director, json={
        "material_change_summary": "The communications dependency changed after approval and may invalidate the continuity assumption.",
        "recommendation": "Prepare a separate proposed plan version for governed review; retain the approved version until replacement is authorized.",
    })
    assert recommendation.status_code == 200, recommendation.text
    rec = recommendation.json()
    assert rec["status"] == "Pending Salus Review"
    assert rec["approved_plan_preserved"] is True
    assert rec["creates_plan_version"] is False and rec["creates_release"] is False
    assert rec["creates_authority"] is False and rec["creates_charge"] is False
    rec_review = client.post(
        f"{create_path}/revision-recommendations/{rec['id']}/review", headers=director,
        json={
            "decision": "Accepted for Drafting",
            "reason": "Authorize preparation of a separate draft only; no approved plan replacement or release.",
        },
    )
    assert rec_review.status_code == 200, rec_review.text
    assert rec_review.json()["status"] == "Accepted for Drafting"
    assert rec_review.json()["creates_plan_version"] is False

    still_approved = client.get(f"/api/salops/preparedness/plans/{plan_id}", headers=director).json()["plan"]
    assert still_approved["status"] == "Approved" and still_approved["version"] == 1
    bundle = client.get(f"{create_path}/{run_id}", headers=director)
    assert bundle.status_code == 200, bundle.text
    assert len(bundle.json()["sources"]) == 2
    assert len(bundle.json()["sections"]) == 1
    assert len(bundle.json()["revision_recommendations"]) == 1
    assert len(bundle.json()["events"]) >= 10

    backup_conn = salcapa_runtime.core.db()
    try:
        records = salcapa_runtime.core.collect_tenant_records(backup_conn, 1)
    finally:
        backup_conn.close()
    for table in (
        "salops_plan_assembly_runs", "salops_plan_assembly_sources",
        "salops_plan_assembly_questions", "salops_plan_assembly_sections",
        "salops_plan_revision_recommendations", "salops_plan_assembly_events",
    ):
        assert table in records and records[table], table
    tampered = {key: list(value) for key, value in records.items()}
    tampered["salops_plan_assembly_runs"] = [dict(records["salops_plan_assembly_runs"][0], tenant_id=2)]
    errors = salcapa_runtime.core.validate_records(tampered, 1)
    assert any("crosses the tenant boundary" in error for error in errors)

    print("SALOPS_AUTONOMOUS_PLAN_ASSEMBLY_PASS")


if __name__ == "__main__":
    main()
