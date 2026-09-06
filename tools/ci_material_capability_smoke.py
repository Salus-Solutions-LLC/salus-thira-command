#!/usr/bin/env python3
"""Acceptance checks for generic governed material records and source links."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "materials.db"))
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
    analyst = {
        "X-Salus-Tenant": "1",
        "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Material Analyst",
    }
    member = {
        "X-Salus-Tenant": "1",
        "X-Salus-Role": "Contributor",
        "X-Salus-User": "Member Submitter",
    }
    other_member = {**member, "X-Salus-User": "Other Member"}
    executive = {**member, "X-Salus-Role": "Client Executive", "X-Salus-User": "Member Executive"}

    content = b"SYNTHETIC GOVERNED SOURCE MATERIAL\n"
    files = {"file": ("source.txt", content, "text/plain")}
    data = {
        "title": "Synthetic source",
        "material_kind": "Document",
        "source_origin": "Authorized synthetic demonstration",
        "source_locator": "demo://source/1",
        "acquired_at": "2026-09-06T00:00:00Z",
        "sensitivity": "Restricted",
        "purpose_tags": json.dumps(["documentation", "analysis"]),
        "description": "Synthetic material for material-record acceptance.",
        "recording_authority_basis": "",
        # These unsupported fields must never control persisted state.
        "tenant_id": "2",
        "processing_status": "Linked / Promoted",
        "disclosure_status": "Approved for Tenant",
        "sha256": "0" * 64,
        "uploaded_by": "forged",
    }
    response = client.post("/api/materials/upload", headers=analyst, data=data, files=files)
    assert response.status_code == 200, response.text
    material = response.json()
    material_id = material["id"]
    assert material["processing_status"] == "Ready for Processing"
    assert material["disclosure_status"] == "Salus Internal"
    assert material["sha256"] == hashlib.sha256(content).hexdigest()
    assert material["uploaded_by"] == "Material Analyst"
    assert material["tenant_id"] == 1
    assert material["purpose_tags"] == ["documentation", "analysis"]
    assert "stored_name" not in material and "scan_detail" not in material
    assert material["immutable_original"] is True

    assert client.get(f"/api/materials/{material_id}", headers=member).status_code == 403
    assert client.post(
        f"/api/materials/{material_id}/transition",
        headers=member,
        json={"status": "Processing", "reason": "Unauthorized member action."},
    ).status_code == 403

    response = client.post(
        f"/api/materials/{material_id}/transition",
        headers=analyst,
        json={"status": "Processing", "reason": "Begin controlled extraction."},
    )
    assert response.status_code == 200, response.text
    response = client.post(
        f"/api/materials/{material_id}/transition",
        headers=analyst,
        json={"status": "Ready for Human Review", "reason": "Processing complete; no authority implied."},
    )
    assert response.status_code == 200, response.text

    conn = app.db()
    assessment_id = int(conn.execute("SELECT id FROM assessments WHERE tenant_id=1 ORDER BY id LIMIT 1").fetchone()["id"])
    conn.close()
    response = client.post(
        f"/api/materials/{material_id}/links",
        headers=analyst,
        json={
            "target_type": "assessment",
            "target_id": assessment_id,
            "purpose": "Human-approved source reference; not an assessment finding.",
        },
    )
    assert response.status_code == 200, response.text
    link = response.json()
    assert link["assessment_id"] == assessment_id
    assert link["linked_by_role"] == "Assessment Director"

    assert client.get(f"/api/materials/{material_id}", headers=member).status_code == 403
    response = client.post(
        f"/api/materials/{material_id}/disclosure",
        headers=analyst,
        json={
            "approved_for_protected_member": True,
            "reason": "Synthetic source approved for this tenant's Protected Member users.",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["disclosure_status"] == "Approved for Tenant"

    visible = client.get(f"/api/materials/{material_id}", headers=member)
    assert visible.status_code == 403  # Restricted exceeds Contributor clearance.
    visible = client.get(f"/api/materials/{material_id}", headers=executive)
    assert visible.status_code == 200, visible.text
    assert visible.json()["links"] == [] and visible.json()["events"] == []

    downloaded = client.get(f"/api/materials/{material_id}/download", headers=analyst)
    assert downloaded.status_code == 200 and downloaded.content == content
    assert downloaded.headers["x-content-sha256"] == hashlib.sha256(content).hexdigest()
    assert downloaded.headers["x-content-type-options"] == "nosniff"

    duplicate = client.post(
        "/api/materials/upload",
        headers=analyst,
        data={
            "title": "Same bytes, distinct source context",
            "material_kind": "Text",
            "source_origin": "Second authorized receipt",
            "purpose_tags": "correlation",
        },
        files={"file": ("another-name.txt", content, "text/plain")},
    )
    assert duplicate.status_code == 200, duplicate.text
    duplicate_id = duplicate.json()["id"]
    assert duplicate_id != material_id
    assert duplicate.json()["duplicate_of_material_id"] == material_id
    conn = app.db()
    stored = [
        row["stored_name"]
        for row in conn.execute(
            "SELECT stored_name FROM materials WHERE id IN (?,?) ORDER BY id",
            (material_id, duplicate_id),
        )
    ]
    assert stored[0] == stored[1]
    conn.close()

    submitted = client.post(
        "/api/materials/upload",
        headers=member,
        data={
            "title": "Member source",
            "material_kind": "Image",
            "source_origin": "Protected Member submission",
        },
        files={"file": ("photo.jpg", b"synthetic-photo", "image/jpeg")},
    )
    assert submitted.status_code == 200, submitted.text
    submitted_id = submitted.json()["id"]
    assert submitted.json()["disclosure_status"] == "Protected Member Submitted"
    assert client.get(f"/api/materials/{submitted_id}", headers=member).status_code == 200
    assert client.get(f"/api/materials/{submitted_id}", headers=other_member).status_code == 403
    assert client.get(f"/api/materials/{submitted_id}", headers=executive).status_code == 200

    conn = app.db()
    conn.execute(
        "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(2,'Other Tenant','other-tenant','Active',?) "
        "ON CONFLICT(id) DO NOTHING",
        (app.now(),),
    )
    conn.commit()
    conn.close()
    tenant_two = {**analyst, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Analyst"}
    assert client.get(f"/api/materials/{material_id}", headers=tenant_two).status_code == 403

    hold = client.patch(
        f"/api/materials/{material_id}/governance",
        headers=analyst,
        json={"legal_hold": True, "reason": "Preserve during synthetic investigation."},
    )
    assert hold.status_code == 200 and hold.json()["legal_hold"] is True
    blocked_disposal = client.patch(
        f"/api/materials/{material_id}/governance",
        headers=analyst,
        json={"disposition_status": "Disposed", "reason": "Attempt disposal under hold."},
    )
    assert blocked_disposal.status_code == 409

    catalog = client.get("/api/materials/catalog", headers=analyst)
    assert catalog.status_code == 200
    assert {item["id"] for item in catalog.json()} >= {material_id, duplicate_id, submitted_id}

    conn = app.db()
    records = collect_tenant_records(conn, 1)
    errors = validate_records(records, 1)
    assert not errors, errors
    assert len(records["materials"]) == 3
    assert len(records["material_links"]) == 1
    assert len(records["material_events"]) >= 7
    replace_tenant_records(conn, 1, records)
    conn.commit()
    restored = {
        table: conn.execute(f"SELECT COUNT(*) c FROM {table} WHERE tenant_id=1").fetchone()["c"]
        for table in ("materials", "material_links", "material_events")
    }
    conn.close()
    assert restored == {table: len(records[table]) for table in restored}

    assert not any(
        forbidden in Path(ROOT / "material_capability.py").read_text(encoding="utf-8")
        for forbidden in ("Personnel Assessment", "Facility Assessment")
    )
    print("SALCAPA_GOVERNED_MATERIALS_PASS", app.DB_BACKEND)


if __name__ == "__main__":
    main()
