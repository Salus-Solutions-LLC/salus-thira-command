#!/usr/bin/env python3
"""Acceptance checks for the governed shared SalINTEL domain model."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "salintel.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
os.environ["SALUS_ALLOW_RESTORE"] = "1"
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app
from portable_backup import collect_tenant_records, replace_tenant_records, validate_records


def main():
    client = TestClient(app.app)
    analyst = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
               "X-Salus-User": "SalINTEL Analyst"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
              "X-Salus-User": "Protected Member User"}

    catalog = client.get("/api/salintel/domains/catalog", headers=analyst)
    assert catalog.status_code == 200, catalog.text
    keys = {row["domain_key"] for row in catalog.json()}
    assert {"personnel-assessment", "facility-assessment", "organizations",
            "critical-dependencies", "defensive-threat-actor"} <= keys
    personnel = next(row for row in catalog.json()
                     if row["domain_key"] == "personnel-assessment")
    assert [row["tier"] for row in personnel["tier_profiles"]] == [1, 2, 3]
    assert personnel["investigative_lenses"] == [
        "Prevention", "Protection", "Mitigation", "Response", "Recovery"]
    assert personnel["version"] == 1
    baseline = client.get("/api/salintel/domains/catalog/personnel-assessment",
                          headers=analyst)
    assert baseline.status_code == 200 and len(baseline.json()["events"]) == 1
    assert client.get("/api/salintel/domains/catalog/personnel-assessment",
                      headers=member).status_code == 403
    forged_domain = client.put("/api/salintel/domains/catalog/personnel-assessment",
        headers=analyst, json={"version": 99, "approved_by": "client"})
    assert forged_domain.status_code == 422
    update_payload = {
        "display_name": personnel["display_name"],
        "description": personnel["description"],
        "subject_entity_kinds": ["person"],
        "lifecycle_status": "Held",
        "default_sensitivity": personnel["default_sensitivity"],
        "default_disclosure_posture": personnel["default_disclosure_posture"],
        "investigative_lenses": personnel["investigative_lenses"],
        "handoff_types": personnel["handoff_types"],
        "allowed_relationships": personnel["allowed_relationships"],
        "required_review_level": personnel["required_review_level"],
        "tier_profiles": [{**item, "profile_version": "personnel-v1"}
                          for item in personnel["tier_profiles"]],
        "reason": "SYNTHETIC governance hold for version-history acceptance.",
    }
    denied_domain = client.put("/api/salintel/domains/catalog/personnel-assessment",
        headers=member, json=update_payload)
    assert denied_domain.status_code == 403
    held = client.put("/api/salintel/domains/catalog/personnel-assessment",
                      headers=analyst, json=update_payload)
    assert held.status_code == 200, held.text
    assert held.json()["version"] == 2 and held.json()["approved_by"] == "SalINTEL Analyst"
    member_keys = {row["domain_key"] for row in client.get(
        "/api/salintel/domains/catalog", headers=member).json()}
    assert "personnel-assessment" not in member_keys
    blocked_request = client.post("/api/salintel/investigations", headers=analyst,
        json={"domain_key": "personnel-assessment", "title": "Held",
              "subject_reference": "SYNTHETIC", "purpose": "Blocked while held",
              "requested_tier": 1})
    assert blocked_request.status_code == 422
    update_payload["lifecycle_status"] = "Enabled"
    update_payload["reason"] = "SYNTHETIC governance re-enable after review."
    enabled_again = client.put("/api/salintel/domains/catalog/personnel-assessment",
                               headers=analyst, json=update_payload)
    assert enabled_again.status_code == 200 and enabled_again.json()["version"] == 3
    history = client.get("/api/salintel/domains/catalog/personnel-assessment",
                         headers=analyst).json()["events"]
    assert [item["version_no"] for item in history] == [1, 2, 3]

    operator = {"X-Salus-Tenant": "1", "X-Salus-Role": "System Administrator",
                "X-Salus-User": "Registry Recovery Operator"}
    reviewer = {**operator, "X-Salus-User": "Independent Registry Reviewer"}
    denied_backup = client.post("/api/salintel/domains/registry-backups", headers=member,
                                json={"reason": "Member must not create backups."})
    assert denied_backup.status_code == 403
    backup = client.post("/api/salintel/domains/registry-backups", headers=operator,
                         json={"reason": "SYNTHETIC registry recovery baseline."})
    assert backup.status_code == 200, backup.text
    backup_id = backup.json()["id"]
    assert "payload_json" not in backup.json()
    verified = client.post(f"/api/salintel/domains/registry-backups/{backup_id}/verify",
                           headers=operator)
    assert verified.status_code == 200 and verified.json()["ok"] is True
    assert verified.json()["domain_count"] == len(catalog.json())
    drift_payload = {**update_payload,
                     "display_name": "SYNTHETIC temporary registry drift",
                     "reason": "SYNTHETIC change that recovery must reverse."}
    drift = client.put("/api/salintel/domains/catalog/personnel-assessment",
                       headers=analyst, json=drift_payload)
    assert drift.status_code == 200 and drift.json()["version"] == 4
    restore_request = client.post(
        "/api/salintel/domains/registry-restore-requests", headers=operator,
        json={"backup_id": backup_id,
              "scope": "Entire enterprise SalINTEL investigative-domain registry",
              "reason": "Reverse synthetic configuration drift."})
    assert restore_request.status_code == 200, restore_request.text
    restore_id = restore_request.json()["id"]
    self_decision = client.post(
        f"/api/salintel/domains/registry-restore-requests/{restore_id}/decision",
        headers=operator,
        json={"decision": "Authorized", "reason": "Self-approval must fail."})
    assert self_decision.status_code == 409
    decision = client.post(
        f"/api/salintel/domains/registry-restore-requests/{restore_id}/decision",
        headers=reviewer,
        json={"decision": "Authorized",
              "reason": "Independent authorization for synthetic recovery."})
    assert decision.status_code == 200 and decision.json()["status"] == "Authorized"
    restored = client.post(
        f"/api/salintel/domains/registry-restore-requests/{restore_id}/execute",
        headers=operator)
    assert restored.status_code == 200, restored.text
    assert restored.json()["ok"] is True
    assert restored.json()["safety_backup_id"] != backup_id
    recovered = client.get("/api/salintel/domains/catalog/personnel-assessment",
                           headers=analyst).json()
    assert recovered["display_name"] == personnel["display_name"]
    assert recovered["version"] == 4
    assert [item["version_no"] for item in recovered["events"]] == [1, 2, 3, 4]
    assert recovered["events"][-1]["event_type"] == "DOMAIN_REGISTRY_RESTORED"
    listed = client.get("/api/salintel/domains/registry-backups", headers=operator)
    assert listed.status_code == 200 and len(listed.json()) == 2
    assert all("payload_json" not in row for row in listed.json())
    conn = app.db()
    assert conn.execute(
        "SELECT COUNT(*) c FROM audit_log "
        "WHERE action='SALINTEL_DOMAIN_REGISTRY_RESTORE_EXECUTED'"
    ).fetchone()["c"] == 1
    conn.close()

    forged = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "organizations", "title": "Forged",
        "subject_reference": "SYNTHETIC", "purpose": "Test",
        "requested_tier": 1, "tenant_id": 2, "authorized_tier": 3,
        "status": "Tier Complete", "disclosure_status": "Approved for Tenant"})
    assert forged.status_code == 422, forged.text

    response = client.post("/api/salintel/investigations", headers=analyst, json={
        "domain_key": "organizations",
        "title": "SYNTHETIC Acme continuity investigation",
        "subject_reference": "SYNTHETIC-ORG-ACME",
        "purpose": "Bounded baseline reliability and dependency review.",
        "requested_tier": 2, "sensitivity": "Standard",
        "engagement_context": "Synthetic Protected Member planning."})
    assert response.status_code == 200, response.text
    record = response.json()
    record_id = record["id"]
    assert record["tenant_id"] == 1 and record["authorized_tier"] == 0
    assert record["status"] == "Requested"
    assert record["qualification_status"] == "Unqualified"
    assert record["disclosure_status"] == "Salus Internal"
    assert record["commercial_treatment"] == "Not Determined"
    assert client.get(f"/api/salintel/investigations/{record_id}",
                      headers=member).status_code == 403

    denied = client.post(
        f"/api/salintel/investigations/{record_id}/authorize-tier",
        headers=member, json={"authorized_tier": 3, "scope_statement": "No",
                              "checklist_version": "v1", "reason": "No"})
    assert denied.status_code == 403

    response = client.post(
        f"/api/salintel/investigations/{record_id}/authorize-tier",
        headers=analyst, json={
            "authorized_tier": 1,
            "scope_statement": "Identity, ownership, core operations, primary dependencies, contradictions, and known unknowns.",
            "checklist_version": "shared-v1",
            "investigative_lenses": ["Protection", "Recovery"],
            "source_categories": ["authorized public records", "member materials"],
            "exclusions": ["deep historical network analysis"],
            "effort_bounds": {"maximum_hours": 4, "history_years": 3},
            "commercial_treatment": "Included",
            "commercial_reference": "SYNTHETIC-SOW-1",
            "reason": "Salus authorized a bounded Tier 1 deliverable."})
    assert response.status_code == 200, response.text
    assert response.json()["authorized_tier"] == 1
    assert response.json()["authorized_scope"]["checklist_version"] == "shared-v1"
    assert response.json()["authorized_scope"]["investigative_lenses"] == ["Protection", "Recovery"]

    premature = client.post(
        f"/api/salintel/investigations/{record_id}/complete-tier",
        headers=analyst, json={"tier": 1,
        "completion_statement": "Premature.", "residual_unknowns": ""})
    assert premature.status_code == 409

    material = client.post("/api/materials/upload", headers=analyst, data={
        "title": "SYNTHETIC organization source", "material_kind": "Document",
        "source_origin": "Authorized synthetic record", "sensitivity": "Standard",
        "purpose_tags": json.dumps(["SalINTEL"])},
        files={"file": ("organization.txt", b"SYNTHETIC SOURCE\n", "text/plain")})
    assert material.status_code == 200, material.text
    material_id = material.json()["id"]
    for state, reason in [
        ("Processing", "Begin governed extraction."),
        ("Ready for Human Review", "Extraction reviewed."),
    ]:
        transition = client.post(f"/api/materials/{material_id}/transition",
                                 headers=analyst,
                                 json={"status": state, "reason": reason})
        assert transition.status_code == 200, transition.text
    linked = client.post(f"/api/materials/{material_id}/links", headers=analyst,
        json={"target_type": "salintel_investigation", "target_id": record_id,
              "purpose": "Human-approved source reference."})
    assert linked.status_code == 200, linked.text

    response = client.post(f"/api/salintel/investigations/{record_id}/items",
        headers=analyst, json={
            "item_kind": "Finding", "epistemic_state": "Verified Fact",
            "title": "SYNTHETIC identity corroborated",
            "detail": "The bounded source set corroborates the synthetic entity.",
            "source_reliability": "Reliable", "information_confidence": "High",
            "source_material_id": material_id})
    assert response.status_code == 200, response.text
    item_id = response.json()["id"]
    gap = client.post(f"/api/salintel/investigations/{record_id}/items",
        headers=analyst, json={
            "item_kind": "Collection Requirement",
            "epistemic_state": "Information Gap",
            "title": "SYNTHETIC alternate supplier detail unresolved",
            "detail": "Tier 1 excluded deep supplier network review.",
            "information_confidence": "Explicit Gap"})
    assert gap.status_code == 200, gap.text

    filtered = client.get("/api/salintel/investigations?epistemic_state=Information%20Gap&phase=Recovery&authorized_tier=1", headers=analyst)
    assert filtered.status_code == 200 and [row["id"] for row in filtered.json()] == [record_id]
    excluded = client.get("/api/salintel/investigations?phase=Response", headers=analyst)
    assert excluded.status_code == 200 and record_id not in [row["id"] for row in excluded.json()]
    assert client.get("/api/salintel/investigations?phase=Invalid", headers=analyst).status_code == 422

    qualified = client.post(f"/api/salintel/investigations/{record_id}/qualify",
        headers=analyst, json={"status": "Qualified",
        "reason": "Human analyst qualified facts and preserved the gap."})
    assert qualified.status_code == 200, qualified.text
    wrong = client.post(f"/api/salintel/investigations/{record_id}/complete-tier",
        headers=analyst, json={"tier": 2, "completion_statement": "Wrong tier."})
    assert wrong.status_code == 409

    response = client.post(f"/api/salintel/investigations/{record_id}/complete-tier",
        headers=analyst, json={"tier": 1,
        "completion_statement": "Authorized Tier 1 scope is complete.",
        "residual_unknowns": "Alternate supplier depth remains unknown."})
    assert response.status_code == 200, response.text
    assert response.json()["completed_tier"] == 1
    recommended = client.post(
        f"/api/salintel/investigations/{record_id}/recommend-tier",
        headers=analyst, json={"recommended": True,
        "reason": "Recommend separately authorized Tier 2 supplier review."})
    assert recommended.status_code == 200
    assert recommended.json()["authorized_tier"] == 1

    disclosure = client.post(
        f"/api/salintel/investigations/{record_id}/disclosure",
        headers=analyst, json={"approved_for_tenant": True,
        "reason": "Release bounded qualified conclusion to this tenant."})
    assert disclosure.status_code == 200, disclosure.text
    blocked = client.post(
        f"/api/salintel/investigations/{record_id}/items/{item_id}/release",
        headers=analyst, json={"approved_for_tenant": True,
        "reason": "Source is not separately approved."})
    assert blocked.status_code == 409
    source_release = client.post(f"/api/materials/{material_id}/disclosure",
        headers=analyst, json={"approved_for_protected_member": True,
        "reason": "Approve synthetic source for this tenant."})
    assert source_release.status_code == 200
    item_release = client.post(
        f"/api/salintel/investigations/{record_id}/items/{item_id}/release",
        headers=analyst, json={"approved_for_tenant": True,
        "reason": "Release qualified synthetic finding."})
    assert item_release.status_code == 200

    member_view = client.get(f"/api/salintel/investigations/{record_id}",
                             headers=member)
    assert member_view.status_code == 200, member_view.text
    shown = member_view.json()
    assert [row["id"] for row in shown["items"]] == [item_id]
    assert shown["events"] == [] and shown["material_links"] == []
    for key in ("enterprise_visibility", "commercial_treatment",
                "commercial_reference", "effort_bounds", "source_categories",
                "exclusions", "created_by", "updated_by", "reviewed_by"):
        assert key not in shown

    conn = app.db()
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) "
                 "VALUES(2,'Other Tenant','other-tenant','Active',?) "
                 "ON CONFLICT(id) DO NOTHING", (app.now(),))
    conn.commit(); conn.close()
    other = {**analyst, "X-Salus-Tenant": "2", "X-Salus-User": "Other Analyst"}
    assert client.get(f"/api/salintel/investigations/{record_id}",
                      headers=other).status_code == 403

    conn = app.db()
    records = collect_tenant_records(conn, 1)
    errors = validate_records(records, 1)
    assert not errors, errors
    assert len(records["salintel_investigations"]) == 1
    assert len(records["salintel_investigation_items"]) == 2
    replace_tenant_records(conn, 1, records)
    conn.commit()
    for table in ("salintel_investigations", "salintel_investigation_items",
                  "salintel_investigation_events"):
        actual = conn.execute(
            f"SELECT COUNT(*) c FROM {table} WHERE tenant_id=1").fetchone()["c"]
        assert actual == len(records[table])
    conn.close()

    detail = client.get(f"/api/salintel/investigations/{record_id}",
                        headers=analyst).json()
    versions = [row["version_no"] for row in detail["events"]]
    assert versions == list(range(1, len(versions) + 1))
    assert detail["completed_tier"] == detail["authorized_tier"] == 1
    print("SALCAPA_SALINTEL_DOMAIN_MODEL_PASS", app.DB_BACKEND)


if __name__ == "__main__":
    main()
