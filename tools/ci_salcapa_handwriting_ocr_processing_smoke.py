#!/usr/bin/env python3
"""Acceptance checks for governed handwriting and difficult-text recognition."""

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
PROFILE_ROOT = Path(WORKSPACE.name) / "approved-handwriting-ocr-profile"; PROFILE_ROOT.mkdir()
RUNNER = PROFILE_ROOT / "local-recognizer"; MODEL = PROFILE_ROOT / "approved-model.bin"; LANGUAGE = PROFILE_ROOT / "approved-language.bin"; MANIFEST = PROFILE_ROOT / "active-profile.json"
RUNNER.write_text("#!/bin/sh\nprintf '%s\\n' '{\"ok\":true,\"segments\":[{\"reading_order\":1,\"text\":\"Meet at 0?30\",\"segment_type\":\"handwritten\",\"score\":0.71,\"region\":{\"x\":12,\"y\":18,\"width\":180,\"height\":40},\"language\":\"English\",\"script\":\"Latin\",\"alternatives\":[\"Meet at 0830\",\"Meet at 0930\"],\"uncertain_spans\":[{\"start\":8,\"end\":9,\"alternatives\":[\"8\",\"9\"],\"reason\":\"Ambiguous visible mark\"}],\"limitations\":\"Faint numeral; do not infer a 24-hour time without review.\"}]}'\n", encoding="utf-8"); RUNNER.chmod(0o500)
MODEL.write_bytes(b"fictional demonstration handwriting model; not operational\n"); LANGUAGE.write_bytes(b"fictional demonstration English Latin language data\n")


def sha(path: Path) -> str: return hashlib.sha256(path.read_bytes()).hexdigest()


profile = {
    "profile_key": "HRO-FICTIONAL-ACCEPTANCE-V1", "name": "Fictional handwriting acceptance profile", "status": "Active",
    "executable_path": str(RUNNER), "executable_sha256": sha(RUNNER), "model_path": str(MODEL), "model_sha256": sha(MODEL),
    "language_data_path": str(LANGUAGE), "language_data_sha256": sha(LANGUAGE), "configuration_sha256": "c" * 64,
    "model_version": "acceptance-1", "model_provenance": "Repository fictional acceptance fixture", "model_license": "Test fixture only",
    "modes": ["Printed text", "Handwritten text", "Mixed text", "Targeted region review"], "languages": ["English"], "scripts": ["Latin"],
    "score_semantics": "Profile ranking score; not truth probability, source reliability, evidentiary weight, or analyst confidence.",
    "preprocessing": {"contract": "identity source-region acceptance fixture"},
    "known_limitations": "Fictional fixture only. Production requires separately approved artifacts and validation.",
    "approved_purposes": ["field note"], "timeout_seconds": 10, "max_segments": 20, "max_characters": 10000,
}
MANIFEST.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")
os.chdir(ROOT); os.environ.update({"SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1", "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"), "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "handwriting.db"), "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"), "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"), "SALUS_HANDWRITING_OCR_PROFILE_ROOT": str(PROFILE_ROOT), "SALUS_HANDWRITING_OCR_PROFILE_MANIFEST": str(MANIFEST)}); sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_handwriting_ocr_processing import register_salcapa_handwriting_ocr_processing  # noqa: E402

register_salcapa_handwriting_ocr_processing(core.app, core.__dict__)
REQUESTER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Recognition Requester"}
REVIEWER = {**REQUESTER, "X-Salus-User": "Independent Source Reviewer"}
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}
STOP_AFTER = os.environ.get("SALUS_HANDWRITING_OCR_STOP_AFTER", "").strip()


def checkpoint(name: str) -> None:
    print(f"SALCAPA_HANDWRITING_OCR_CHECKPOINT {name}")
    if STOP_AFTER == name:
        raise SystemExit(0)


def image_bytes() -> bytes:
    # Each isolated PostgreSQL phase receives its own governed object. Reusing an
    # identical digest would legitimately deduplicate to a prior phase's record
    # after that phase's temporary object store has been removed.
    color_seed = hashlib.sha256(WORKSPACE.name.encode("utf-8")).digest()
    image = Image.new("RGB", (320, 240), tuple(color_seed[:3])); output = io.BytesIO(); image.save(output, "PNG"); return output.getvalue()


with TestClient(core.app) as client:
    upload = client.post("/api/materials/upload", headers=REQUESTER, files={"file": ("fictional-field-note.png", image_bytes(), "image/png")}, data={"title": "Fictional field note", "material_kind": "Image", "source_origin": "Authorized fictional demonstration", "sensitivity": "Restricted"})
    assert upload.status_code == 200, upload.text; source = upload.json()
    status = client.get("/api/handwriting-ocr/status", headers=REQUESTER); assert status.status_code == 200 and status.json()["available"] is True
    assert status.json()["external_processing"] is False and status.json()["manual_transcription_available"] is True
    assert client.get("/api/handwriting-ocr/status", headers=MEMBER).status_code == 403
    checkpoint("status")
    assert client.post(f"/api/materials/{source['id']}/handwriting-ocr-jobs", headers=REQUESTER, json={"purpose": "Unapproved general processing", "mode": "Handwritten text"}).status_code == 403
    checkpoint("purpose")
    assert client.post(f"/api/materials/{source['id']}/handwriting-ocr-jobs", headers=REQUESTER, json={"purpose": "Review a field note", "mode": "Targeted region review"}).status_code == 422
    checkpoint("region")
    prepared = client.post(f"/api/materials/{source['id']}/handwriting-ocr-jobs", headers=REQUESTER, json={"purpose": "Review the fictional field note", "mode": "Handwritten text", "region_x": 20, "region_y": 10, "region_width": 250, "region_height": 100})
    assert prepared.status_code == 200, prepared.text
    checkpoint("response")
    body = prepared.json(); job, segment = body["job"], body["segments"][0]
    assert job["external_processing"] == 0 and job["route"] == "Approved local profile" and job["segment_count"] == 1
    assert all(len(job[field]) == 64 for field in ("profile_snapshot_sha256", "model_sha256", "language_data_sha256", "configuration_sha256"))
    checkpoint("job")
    assert segment["record_type"] == "Prepared Text — Derived and Unverified" and segment["review_status"] == "Awaiting Human Review"
    assert segment["original_text"] == "Meet at 0?30" and segment["region_x"] == 32 and segment["region_y"] == 28
    assert segment["alternatives"] == ["Meet at 0830", "Meet at 0930"] and segment["uncertain_spans"][0]["reason"] == "Ambiguous visible mark"
    checkpoint("prepared")
    assert client.post(f"/api/handwriting-ocr/segments/{segment['id']}/review", headers=REQUESTER, json={"status": "Confirm Representation", "reason": "Self-review must fail."}).status_code == 409
    assert client.post(f"/api/handwriting-ocr/segments/{segment['id']}/review", headers=OTHER, json={"status": "Confirm Representation", "reason": "Cross-tenant review must fail."}).status_code == 403
    reviewed = client.post(f"/api/handwriting-ocr/segments/{segment['id']}/review", headers=REVIEWER, json={"status": "Correct", "reason": "Compared each visible mark with the fictional source.", "corrected_text": "Meet at 0830", "limitations": "The source does not establish the date."})
    assert reviewed.status_code == 200 and reviewed.json()["review_status"] == "Correct" and reviewed.json()["original_text"] == "Meet at 0?30"
    triage = client.get("/api/handwriting-ocr/triage", headers=REVIEWER); assert triage.status_code == 200 and triage.json()["items"][0]["review_status"] == "Correct"
    checkpoint("reviewed")
    if os.environ.get("SALUS_DB_BACKEND", "sqlite") == "sqlite":
        records = core.collect_tenant_records(core.db(), 1)
        for table in ("handwriting_ocr_jobs", "handwriting_ocr_segments", "handwriting_ocr_reviews"): assert records[table]
        validation_errors = core.validate_records(records, 1)
        assert validation_errors == []
        tampered = copy.deepcopy(records); tampered["handwriting_ocr_jobs"][0]["language_data_sha256"] = "bad"
        assert any("invalid language_data_sha256" in error for error in core.validate_records(tampered, 1))
    else:
        conn = core.db()
        try:
            for table in ("handwriting_ocr_jobs", "handwriting_ocr_segments", "handwriting_ocr_reviews"):
                assert int(conn.execute(f"SELECT COUNT(*) c FROM {table} WHERE tenant_id=?", (1,)).fetchone()["c"]) > 0
        finally:
            conn.close()
    checkpoint("persistence")
    LANGUAGE.write_bytes(b"tampered"); disabled = client.get("/api/handwriting-ocr/status", headers=REQUESTER).json(); assert disabled["available"] is False and "does not match" in disabled["guidance"]
    manual = client.post(f"/api/materials/{source['id']}/manual-transcriptions", headers=REQUESTER, json={"purpose": "Review the fictional field note manually", "transcription": "[Illegible] at 0830", "segment_type": "handwritten", "limitations": "First word remains illegible."})
    assert manual.status_code == 200, manual.text
    assert manual.json()["job"]["route"] == "Human-entered manual transcription"
    assert manual.json()["segment"]["review_status"] == "Awaiting Human Review"
    checkpoint("manual")

module = (ROOT / "salcapa_handwriting_ocr_processing.py").read_text(encoding="utf-8"); worker = (ROOT / "tools/salcapa_handwriting_ocr_worker.py").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "shell=True", "http://", "https://"): assert forbidden not in module + worker
for prohibited in ("authorship", "signature", "identity", "personality", "health", "credibility", "intent"): assert prohibited in module.lower()
ui = (ROOT / "static/salcapa-handwriting-ocr.js").read_text(encoding="utf-8").lower()
for phrase in ("extract printed text", "review handwriting", "compare with original", "record manual transcription", "derived and unverified"): assert phrase in ui
print("SALCAPA_HANDWRITING_OCR_PROCESSING_SMOKE_PASS")
