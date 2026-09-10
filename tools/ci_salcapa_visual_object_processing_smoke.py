#!/usr/bin/env python3
"""Acceptance checks for governed local object and condition suggestions."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import sys

from fastapi.testclient import TestClient
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
PROFILE_ROOT = Path(WORKSPACE.name) / "approved-visual-profile"
PROFILE_ROOT.mkdir()
RUNNER = PROFILE_ROOT / "local-processor"
MODEL = PROFILE_ROOT / "approved-model.bin"
MANIFEST = PROFILE_ROOT / "active-profile.json"
RUNNER.write_text(
    "#!/bin/sh\nprintf '%s\\n' '{\"ok\":true,\"detections\":[{\"category_id\":\"door\",\"score\":0.875,\"region\":{\"x\":12,\"y\":18,\"width\":80,\"height\":140},\"alternatives\":[\"opening\"],\"limitations\":\"Partial occlusion; field condition is not established.\"}]}'\n",
    encoding="utf-8",
)
RUNNER.chmod(0o500)
MODEL.write_bytes(b"fictional demonstration model artifact; not an operational model\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


profile = {
    "profile_key": "VOP-FICTIONAL-ACCEPTANCE-V1", "name": "Fictional acceptance processor",
    "status": "Active", "executable_path": str(RUNNER), "executable_sha256": sha(RUNNER),
    "model_path": str(MODEL), "model_sha256": sha(MODEL), "model_version": "acceptance-1",
    "model_provenance": "Repository acceptance fixture", "model_license": "Test fixture only",
    "configuration_sha256": "c" * 64,
    "vocabulary": [{"id": "door", "label": "Door"}, {"id": "opening", "label": "Opening"}],
    "score_semantics": "Processor ranking score within this profile; not real-world probability or evidence strength.",
    "preprocessing": {"contract": "identity RGB source-region acceptance fixture"},
    "known_limitations": "Acceptance fixture only. Production requires a separately approved model artifact and validation record.",
    "approved_purposes": ["facility"], "timeout_seconds": 10,
}
MANIFEST.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")

os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "visual-object.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
    "SALUS_VISUAL_PROFILE_ROOT": str(PROFILE_ROOT),
    "SALUS_VISUAL_PROFILE_MANIFEST": str(MANIFEST),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_visual_geospatial import register_salcapa_visual_geospatial  # noqa: E402
from salcapa_visual_object_processing import register_salcapa_visual_object_processing  # noqa: E402

register_salcapa_visual_geospatial(core.app, core.__dict__)
register_salcapa_visual_object_processing(core.app, core.__dict__)

REQUESTER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Visual Requester"}
REVIEWER = {**REQUESTER, "X-Salus-User": "Independent Visual Reviewer"}
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


def image_bytes() -> bytes:
    image = Image.new("RGB", (320, 240), "white")
    output = io.BytesIO(); image.save(output, "PNG"); return output.getvalue()


with TestClient(core.app) as client:
    upload = client.post(
        "/api/materials/upload", headers=REQUESTER,
        files={"file": ("fictional-facility.png", image_bytes(), "image/png")},
        data={"title": "Fictional facility image", "material_kind": "Image", "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted"},
    )
    assert upload.status_code == 200, upload.text
    source = upload.json()

    status = client.get("/api/visual-object-analysis/status", headers=REQUESTER)
    assert status.status_code == 200 and status.json()["available"] is True
    assert status.json()["external_processing"] is False and status.json()["manual_review_available"] is True
    assert client.get("/api/visual-object-analysis/status", headers=MEMBER).status_code == 403

    outside = client.post(
        f"/api/materials/{source['id']}/visual-object-analysis-jobs", headers=REQUESTER,
        json={"purpose": "Unapproved general-purpose processing."},
    )
    assert outside.status_code == 403

    prepared = client.post(
        f"/api/materials/{source['id']}/visual-object-analysis-jobs", headers=REQUESTER,
        json={"purpose": "Review visible access conditions for the fictional facility.", "region_x": 20, "region_y": 10, "region_width": 200, "region_height": 200},
    )
    assert prepared.status_code == 200, prepared.text
    body = prepared.json(); job = body["job"]; suggestion = body["suggestions"][0]
    assert job["external_processing"] == 0 and job["outcome"] == "Completed" and job["suggestion_count"] == 1
    assert len(job["profile_snapshot_sha256"]) == 64 and len(job["model_sha256"]) == 64
    assert suggestion["record_type"] == "Processing Suggestion — Derived and Unverified"
    assert suggestion["review_status"] == "Awaiting Human Review" and suggestion["display_label"] == "Door"
    assert suggestion["region_x"] == 32 and suggestion["region_y"] == 28
    assert suggestion["alternatives"] == ["opening"]

    assert client.post(
        f"/api/visual-object-analysis/suggestions/{suggestion['id']}/review", headers=REQUESTER,
        json={"status": "Confirm Representation", "reason": "Self-review must fail."},
    ).status_code == 409
    assert client.post(
        f"/api/visual-object-analysis/suggestions/{suggestion['id']}/review", headers=OTHER,
        json={"status": "Confirm Representation", "reason": "Cross-tenant review must fail."},
    ).status_code == 403
    reviewed = client.post(
        f"/api/visual-object-analysis/suggestions/{suggestion['id']}/review", headers=REVIEWER,
        json={"status": "Correct", "reason": "Compared the bounded region with the fictional source.", "corrected_label": "Exterior door", "limitations": "Operability is not established."},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["review_status"] == "Correct"

    triage = client.get("/api/visual-object-analysis/triage", headers=REVIEWER)
    assert triage.status_code == 200 and triage.json()["items"][0]["review_status"] == "Correct"
    assert "missing suggestion does not prove absence" in triage.json()["guidance"]

    records = core.collect_tenant_records(core.db(), 1)
    for table in ("visual_object_jobs", "visual_object_suggestions", "visual_object_reviews"):
        assert records[table]
    assert core.validate_records(records, 1) == []
    tampered = copy.deepcopy(records); tampered["visual_object_jobs"][0]["model_sha256"] = "bad"
    assert any("invalid processor lineage" in error for error in core.validate_records(tampered, 1))

    MODEL.write_bytes(b"tampered")
    disabled = client.get("/api/visual-object-analysis/status", headers=REQUESTER).json()
    assert disabled["available"] is False and "does not match" in disabled["guidance"]

module = (ROOT / "salcapa_visual_object_processing.py").read_text(encoding="utf-8")
worker = (ROOT / "tools/salcapa_visual_object_worker.py").read_text(encoding="utf-8")
ui = (ROOT / "static/salcapa-visual-geospatial.js").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "shell=True", "http://", "https://"):
    assert forbidden not in module + worker
for phrase in (
    "Identify visible conditions", "Compare with original", "Processing Suggestions",
    "salcapaVisualObjectData.guidance", "derived and unverified",
):
    assert phrase.lower() in ui.lower(), phrase

print("SALCAPA_VISUAL_OBJECT_PROCESSING_SMOKE_PASS")
