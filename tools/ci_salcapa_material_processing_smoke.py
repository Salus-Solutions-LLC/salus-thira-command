#!/usr/bin/env python3
"""Acceptance checks for safe derived processing, search, and human triage."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "material-processing.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app as core
from salcapa_material_processing import register_salcapa_material_processing


def main() -> None:
    register_salcapa_material_processing(core.app, core.__dict__)
    client = TestClient(core.app)
    processor = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Processing Lead"}
    reviewer = {**processor, "X-Salus-User": "Independent Reviewer"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Member Contributor"}
    other = {**processor, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}

    source_bytes = b"Generator endurance assumption needs field validation.\nAlternate fuel vendor not yet confirmed."
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    upload = client.post(
        "/api/materials/upload", headers=processor,
        data={
            "title": "Fictional continuity notes", "material_kind": "Text",
            "source_origin": "Authorized demonstration submission", "sensitivity": "Restricted",
            "purpose_tags": json.dumps(["Continuity", "Demonstration"]),
        },
        files={"file": ("continuity.txt", source_bytes, "text/plain")},
    )
    assert upload.status_code == 200, upload.text
    material_id = int(upload.json()["id"])
    assert upload.json()["sha256"] == source_hash

    forbidden = client.post(
        f"/api/materials/{material_id}/safe-text-processing", headers=processor,
        json={"reason": "Prepare an inert derived representation for human review.", "processor": "user-selected", "verified": True},
    )
    assert forbidden.status_code == 422, forbidden.text
    processed = client.post(
        f"/api/materials/{material_id}/safe-text-processing", headers=processor,
        json={"reason": "Prepare an inert derived representation for human review."},
    )
    assert processed.status_code == 200, processed.text
    result = processed.json()
    derivative = result["derivative"]
    assert result["job"]["status"] == "Completed"
    assert derivative["source_sha256"] == source_hash
    assert derivative["confidence_status"] == "Derived — Unverified"
    assert derivative["review_status"] == "Awaiting Human Review"
    derivative_id = int(derivative["id"])

    download = client.get(f"/api/materials/{material_id}/download", headers=processor)
    assert download.status_code == 200 and download.content == source_bytes
    assert download.headers["X-Content-SHA256"] == source_hash
    conn = core.db()
    source = conn.execute("SELECT * FROM materials WHERE id=?", (material_id,)).fetchone()
    assert source["processing_status"] == "Ready for Human Review"
    assert source["sha256"] == source_hash and int(source["immutable_original"]) == 1
    assert conn.execute("SELECT COUNT(*) c FROM material_derivatives WHERE source_material_id=?", (material_id,)).fetchone()["c"] == 1
    assert conn.execute("SELECT COUNT(*) c FROM material_links WHERE material_id=?", (material_id,)).fetchone()["c"] == 0
    portable = core.collect_tenant_records(conn, 1)
    assert len(portable["material_processing_jobs"]) == 1
    assert len(portable["material_derivatives"]) == 1
    assert len(portable["material_derivative_events"]) == 1
    assert core.validate_records(portable, 1) == []
    conn.close()

    search = client.get("/api/material-processing/search?q=endurance", headers=reviewer)
    assert search.status_code == 200, search.text
    assert len(search.json()["items"]) == 1
    assert "field validation" in search.json()["items"][0]["match_excerpt"]
    assert client.get("/api/material-processing/search?q=endurance", headers=member).status_code == 403
    assert client.get("/api/material-processing/search?q=endurance", headers=other).json()["items"] == []
    assert client.get(f"/api/material-processing/derivatives/{derivative_id}", headers=other).status_code == 403

    self_review = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review", headers=processor,
        json={"status": "Human Reviewed", "reason": "Compared with the source."},
    )
    assert self_review.status_code == 409, self_review.text
    reviewed = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review", headers=reviewer,
        json={"status": "Human Reviewed", "reason": "Compared line by line with the unchanged source; this confirms representation only."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "Human Reviewed"
    assert "does not establish" in reviewed.json()["authority_note"]

    pdf_bytes = b"%PDF-1.4\nFictional demonstration placeholder"
    unsupported = client.post(
        "/api/materials/upload", headers=processor,
        data={"title": "Unsupported stage", "material_kind": "Document", "source_origin": "Demonstration"},
        files={"file": ("plan.pdf", pdf_bytes, "application/pdf")},
    )
    assert unsupported.status_code == 200, unsupported.text
    unsupported_id = int(unsupported.json()["id"])
    failed = client.post(
        f"/api/materials/{unsupported_id}/safe-text-processing", headers=processor,
        json={"reason": "Confirm safe unsupported-format handling."},
    )
    assert failed.status_code == 422, failed.text
    conn = core.db()
    failed_source = conn.execute("SELECT * FROM materials WHERE id=?", (unsupported_id,)).fetchone()
    failed_job = conn.execute("SELECT * FROM material_processing_jobs WHERE source_material_id=? ORDER BY id DESC LIMIT 1", (unsupported_id,)).fetchone()
    assert failed_source["processing_status"] == "Ready for Processing"
    assert failed_job["status"] == "Failed" and failed_job["failure_code"] == "FORMAT_NOT_SUPPORTED"
    assert conn.execute("SELECT COUNT(*) c FROM material_derivatives WHERE source_material_id=?", (unsupported_id,)).fetchone()["c"] == 0
    conn.close()

    administrator = {**processor, "X-Salus-Role": "System Administrator", "X-Salus-User": "Recovery Custodian"}
    backup = client.post("/api/admin/backups", headers=administrator)
    assert backup.status_code == 200, backup.text
    backup_id = int(backup.json()["id"])
    verified_backup = client.post(f"/api/admin/backups/{backup_id}/verify", headers=administrator)
    assert verified_backup.status_code == 200 and verified_backup.json()["ok"], verified_backup.text
    recovery_check = client.post(f"/api/admin/backups/{backup_id}/dr-validate", headers=administrator)
    assert recovery_check.status_code == 200 and recovery_check.json()["ok"], recovery_check.text

    js = (ROOT / "static" / "salcapa-material-review.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "salcapa-material-review.css").read_text(encoding="utf-8")
    runtime = (ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
    for required in (
        "Information Review", "People retain authority", "Awaiting Human Review",
        "Search information", "does not establish", "material_review",
    ):
        assert required in js, required
    for forbidden_word in ("AI Review", "AI recommendation", "Automatically verified"):
        assert forbidden_word not in js
    assert "@media print" in css
    assert "salcapa-material-review.js" in runtime and "salcapa-material-review.css" in runtime
    print("SALCAPA_MATERIAL_PROCESSING_PASS", core.DB_BACKEND)


if __name__ == "__main__":
    main()
