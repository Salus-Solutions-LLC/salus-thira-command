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
