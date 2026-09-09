#!/usr/bin/env python3
"""Acceptance checks for governed contextual material capture."""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "contextual-intake.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app as core
from salcapa_contextual_intake import register_salcapa_contextual_intake


def main() -> None:
    register_salcapa_contextual_intake(core.app, core.__dict__)
    client = TestClient(core.app)
    analyst = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director",
        "X-Salus-User": "Context Analyst",
    }
    contributor = {
        "X-Salus-Tenant": "1", "X-Salus-Role": "Contributor",
        "X-Salus-User": "Member Contributor",
    }
    other_tenant = {**analyst, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant"}

    conn = core.db()
    assessment_id = int(conn.execute(
        "SELECT id FROM assessments WHERE tenant_id=1 ORDER BY id LIMIT 1"
    ).fetchone()["id"])
    conn.execute(
        "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(2,'Other Tenant','context-other','Active',?) "
        "ON CONFLICT(id) DO NOTHING", (core.now(),),
    )
    other_assessment = conn.execute(
        "SELECT id FROM assessments WHERE tenant_id=2 ORDER BY id LIMIT 1"
    ).fetchone()
    if not other_assessment:
        cursor = conn.execute(
            "INSERT INTO assessments(tenant_id,name,organization,assessment_type,status,purpose,mission,scope,exclusions,executive_sponsor,assessment_director,lead_assessor,target_completion,reassessment_date,classification,scope_locked,version,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (2,"Other assessment","Other Tenant","Enterprise","Draft","Test","Test","Test","","","","","","","Standard",0,1,core.now(),core.now()),
        )
        other_assessment_id = int(cursor.lastrowid)
    else:
        other_assessment_id = int(other_assessment["id"])
    conn.commit(); conn.close()

    upload = client.post(
        "/api/materials/upload", headers=contributor,
        data={
            "title": "Contextual demonstration source", "material_kind": "Document",
            "source_origin": "Authorized demonstration submission",
            "source_locator": f"salcapa://assessment/{assessment_id}",
            "purpose_tags": json.dumps(["Documentation"]),
        },
        files={"file": ("context.txt", b"Fictional demonstration source", "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    material_id = int(upload.json()["id"])

    proposal = client.post(
        f"/api/materials/{material_id}/context-proposals", headers=contributor,
        json={
            "target_type": "assessment", "target_id": assessment_id,
            "context_label": "Current SalTHIRA assessment",
            "purpose": "Source material submitted from the current assessment workspace",
            "tenant_id": 2, "authoritative_link": True,
        },
    )
    assert proposal.status_code == 422, proposal.text
    proposal = client.post(
        f"/api/materials/{material_id}/context-proposals", headers=contributor,
        json={
            "target_type": "assessment", "target_id": assessment_id,
            "context_label": "Current SalTHIRA assessment",
            "purpose": "Source material submitted from the current assessment workspace",
        },
    )
    assert proposal.status_code == 200, proposal.text
    assert proposal.json()["proposal_state"] == "Awaiting Human Review"
    assert proposal.json()["authoritative_link"] is False

    conn = core.db()
    assert conn.execute(
        "SELECT COUNT(*) c FROM material_links WHERE material_id=?", (material_id,)
    ).fetchone()["c"] == 0
    event = conn.execute(
        "SELECT * FROM material_events WHERE material_id=? AND event_type='CONTEXT_PROPOSED' ORDER BY id DESC LIMIT 1",
        (material_id,),
    ).fetchone()
    audit = conn.execute(
        "SELECT * FROM audit_log WHERE entity_type='material' AND entity_id=? AND action='MATERIAL_CONTEXT_PROPOSED' ORDER BY id DESC LIMIT 1",
        (material_id,),
    ).fetchone()
    conn.close()
    assert event and audit
    assert json.loads(event["reason"])["authoritative_link"] is False

    denied = client.post(
        f"/api/materials/{material_id}/context-proposals", headers=contributor,
        json={
            "target_type": "assessment", "target_id": other_assessment_id,
            "context_label": "Wrong tenant", "purpose": "Boundary test",
        },
    )
    assert denied.status_code == 403, denied.text
    assert client.post(
        f"/api/materials/{material_id}/context-proposals", headers=other_tenant,
        json={
            "target_type": "assessment", "target_id": other_assessment_id,
            "context_label": "Wrong tenant material", "purpose": "Boundary test",
        },
    ).status_code == 403

    js = (ROOT / "static" / "salcapa-contextual-intake.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "salcapa-contextual-intake.css").read_text(encoding="utf-8")
    runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
    for required in (
        "＋ Attach information here", "/api/materials/upload", "/context-proposals",
        "Human review and governed linking are next", "source_locator",
        "salintel_investigation", "assessment", "activeAssessmentId",
    ):
        assert required in js, required
    for forbidden in ("tenant_id", "authoritative_link", "processing_status", "disclosure_status"):
        assert forbidden not in js, forbidden
    assert ".contextual-intake-action" in css and "@media print" in css
    assert "salcapa-contextual-intake.js" in runtime
    assert "salcapa-contextual-intake.css" in runtime
    print("SALCAPA_CONTEXTUAL_INTAKE_PASS", core.DB_BACKEND)


if __name__ == "__main__":
    main()

