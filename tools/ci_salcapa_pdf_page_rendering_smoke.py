#!/usr/bin/env python3
"""Acceptance checks for governed, selected-page PDF rendering."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
PROFILE_ROOT = Path(WORKSPACE.name) / "approved-pdf-render-profile"
PROFILE_ROOT.mkdir()
RENDERER = PROFILE_ROOT / "pdftoppm"
installed_renderer = "/usr/bin/pdftoppm" if Path("/usr/bin/pdftoppm").is_file() else shutil.which("pdftoppm")
assert installed_renderer, "pdftoppm is required for the bounded PDF rendering acceptance"
shutil.copy2(installed_renderer, RENDERER)
RENDERER.chmod(0o500)
MANIFEST = PROFILE_ROOT / "active-profile.json"


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha_file(path: Path) -> str:
    return sha_bytes(path.read_bytes())


profile = {
    "profile_key": "PDR-FICTIONAL-ACCEPTANCE-V1",
    "name": "Fictional selected-page rendering acceptance profile",
    "status": "Active",
    "executable_path": str(RENDERER),
    "executable_sha256": sha_file(RENDERER),
    "renderer_version": "pdftoppm acceptance fixture",
    "renderer_provenance": "Debian package copied into the private acceptance profile",
    "renderer_license": "GPL-2.0-or-later; acceptance environment only",
    "configuration_sha256": "c" * 64,
    "approved_purposes": ["scanned page", "handwriting", "layout"],
    "dpi": 150,
    "color_mode": "RGB",
    "output_format": "PNG",
    "max_pages": 12,
    "max_pixels_per_page": 40_000_000,
    "max_total_pixels": 120_000_000,
    "max_output_bytes_per_page": 64 * 1024 * 1024,
    "max_total_output_bytes": 128 * 1024 * 1024,
    "timeout_seconds": 30,
    "known_limitations": "Compare rendered pages with the original PDF; rendering does not establish source truth.",
    "external_processing": False,
    "no_network": True,
}
MANIFEST.write_text(json.dumps(profile, sort_keys=True), encoding="utf-8")
OCR_PROFILE_ROOT = Path(WORKSPACE.name) / "approved-handwriting-ocr-profile"
OCR_PROFILE_ROOT.mkdir()
OCR_RUNNER = OCR_PROFILE_ROOT / "local-recognizer"
OCR_MODEL = OCR_PROFILE_ROOT / "approved-model.bin"
OCR_LANGUAGE = OCR_PROFILE_ROOT / "approved-language.bin"
OCR_MANIFEST = OCR_PROFILE_ROOT / "active-profile.json"
OCR_RUNNER.write_text(
    "#!/bin/sh\nprintf '%s\\n' '{\"ok\":true,\"segments\":[{\"reading_order\":1,\"text\":\"Meet at 0?30\",\"segment_type\":\"handwritten\",\"score\":0.71,\"region\":{\"x\":12,\"y\":18,\"width\":180,\"height\":40},\"language\":\"English\",\"script\":\"Latin\",\"alternatives\":[\"Meet at 0830\",\"Meet at 0930\"],\"uncertain_spans\":[{\"start\":8,\"end\":9,\"alternatives\":[\"8\",\"9\"],\"reason\":\"Ambiguous visible mark\"}],\"limitations\":\"Faint numeral; compare with the exact PDF page.\"}]}'\n",
    encoding="utf-8",
)
OCR_RUNNER.chmod(0o500)
OCR_MODEL.write_bytes(b"fictional demonstration handwriting model; not operational\n")
OCR_LANGUAGE.write_bytes(b"fictional demonstration English Latin language data\n")
ocr_profile = {
    "profile_key": "HRO-PDF-FICTIONAL-ACCEPTANCE-V1", "name": "Fictional PDF-page recognition profile", "status": "Active",
    "executable_path": str(OCR_RUNNER), "executable_sha256": sha_file(OCR_RUNNER),
    "model_path": str(OCR_MODEL), "model_sha256": sha_file(OCR_MODEL),
    "language_data_path": str(OCR_LANGUAGE), "language_data_sha256": sha_file(OCR_LANGUAGE),
    "configuration_sha256": "d" * 64, "model_version": "acceptance-1",
    "model_provenance": "Repository fictional acceptance fixture", "model_license": "Test fixture only",
    "modes": ["Printed text", "Handwritten text", "Mixed text"], "languages": ["English"], "scripts": ["Latin"],
    "score_semantics": "Profile ranking score; not truth probability, source reliability, evidentiary weight, or analyst confidence.",
    "preprocessing": {"contract": "identity rendered-page acceptance fixture"},
    "known_limitations": "Fictional fixture only. Compare prepared text with the exact rendered PDF page.",
    "approved_purposes": ["handwriting"], "timeout_seconds": 10, "max_segments": 20, "max_characters": 10000,
}
OCR_MANIFEST.write_text(json.dumps(ocr_profile, sort_keys=True), encoding="utf-8")
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype",
    "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": os.environ.get("SALUS_DB_BACKEND", "sqlite"),
    "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "pdf-rendering.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
    "SALUS_PDF_RENDER_PROFILE_ROOT": str(PROFILE_ROOT),
    "SALUS_PDF_RENDER_PROFILE_MANIFEST": str(MANIFEST),
    "SALUS_HANDWRITING_OCR_PROFILE_ROOT": str(OCR_PROFILE_ROOT),
    "SALUS_HANDWRITING_OCR_PROFILE_MANIFEST": str(OCR_MANIFEST),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_pdf_processing import register_salcapa_pdf_processing  # noqa: E402
from salcapa_pdf_page_rendering import _affine, register_salcapa_pdf_page_rendering  # noqa: E402
from salcapa_handwriting_ocr_processing import register_salcapa_handwriting_ocr_processing  # noqa: E402


def fictional_pdf(texts: list[str]) -> bytes:
    writer = PdfWriter()
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    for text in texts:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
        })
        if text:
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream = DecodedStreamObject()
            stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client: TestClient, headers: dict[str, str], name: str, data: bytes, content_type: str = "application/pdf") -> dict:
    response = client.post(
        "/api/materials/upload",
        headers=headers,
        data={
            "title": f"Fictional {name} source",
            "material_kind": "Document",
            "source_origin": "Authorized fictional demonstration",
            "sensitivity": "Restricted",
        },
        files={"file": (name, data, content_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def fictional_png() -> bytes:
    image = Image.new("RGB", (32, 32), (18, 68, 83))
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def apply_transform(matrix: list[float], x: float, y: float) -> tuple[float, float]:
    a, b, c, d, e, f = matrix
    return a * x + b * y + c, d * x + e * y + f


register_salcapa_pdf_processing(core.app, core.__dict__)
register_salcapa_handwriting_ocr_processing(core.app, core.__dict__)
register_salcapa_pdf_page_rendering(core.app, core.__dict__)
conn = core.db()
try:
    if not conn.execute("SELECT id FROM tenants WHERE id=2").fetchone():
        conn.execute(
            "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)",
            (2, "Other Fictional Tenant", "other-fictional-tenant", "Active", core.now()),
        )
    conn.commit()
finally:
    conn.close()
REQUESTER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Page Review Requester"}
REVIEWER = {**REQUESTER, "X-Salus-User": "Independent PDF Page Reviewer"}
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


with TestClient(core.app) as client:
    status = client.get("/api/pdf-page-rendering/status", headers=REQUESTER)
    assert status.status_code == 200 and status.json()["available"] is True, status.text
    assert status.json()["recognition_available"] is True
    assert status.json()["external_processing"] is False
    assert status.json()["rendered_bytes_posture"] == "Ephemeral — Deleted After Validation"
    assert client.get("/api/pdf-page-rendering/status", headers=MEMBER).status_code == 403

    source_bytes = fictional_pdf(["Embedded continuity record", "", "Visible layout review"])
    source = upload(client, REQUESTER, "fictional-scanned-record.pdf", source_bytes)
    other_source = upload(client, OTHER, "other-tenant.pdf", fictional_pdf([""]))
    image_source = upload(client, REQUESTER, "not-a-pdf.png", fictional_png(), "image/png")
    endpoint = f"/api/materials/{source['id']}/pdf-render-jobs"
    assert client.post(endpoint, headers=REQUESTER, json={"purpose": "unapproved processing", "pages": [{"page_number": 2, "reason": "No Embedded Text"}]}).status_code == 403
    assert client.post(endpoint, headers=REQUESTER, json={"purpose": "Review scanned page", "pages": [{"page_number": 2, "reason": "No Embedded Text"}, {"page_number": 2, "reason": "Layout Review Needed"}]}).status_code == 422
    assert client.post(endpoint, headers=REQUESTER, json={"purpose": "Review scanned page", "pages": [{"page_number": 99, "reason": "No Embedded Text"}]}).status_code == 422
    assert client.post(endpoint, headers=REQUESTER, json={"purpose": "Review scanned page", "pages": [{"page_number": 1, "reason": "No Embedded Text"}]}).status_code == 422
    assert client.post(f"/api/materials/{other_source['id']}/pdf-render-jobs", headers=REQUESTER, json={"purpose": "Review scanned page", "pages": [{"page_number": 1, "reason": "No Embedded Text"}]}).status_code == 403
    assert client.post(f"/api/materials/{image_source['id']}/pdf-render-jobs", headers=REQUESTER, json={"purpose": "Review scanned page", "pages": [{"page_number": 1, "reason": "No Embedded Text"}]}).status_code == 422

    before = set(Path(tempfile.gettempdir()).glob("salcapa-pdf-render-*"))
    rendered = client.post(endpoint, headers=REQUESTER, json={
        "purpose": "Review scanned page handwriting and layout",
        "pages": [
            {"page_number": 2, "reason": "No Embedded Text", "recognition_mode": "Handwritten text"},
            {"page_number": 1, "reason": "Layout Review Needed"},
        ],
    })
    assert rendered.status_code == 200, rendered.text
    assert set(Path(tempfile.gettempdir()).glob("salcapa-pdf-render-*")) == before
    body = rendered.json()
    job, pages = body["job"], body["pages"]
    assert job["source_sha256"] == sha_bytes(source_bytes)
    assert job["external_processing"] == 0 and job["network_allowed"] == 0
    assert job["page_count"] == 2 and job["outcome"] == "Completed"
    assert job["rendered_bytes_posture"] == "Ephemeral — Deleted After Validation"
    assert all(len(job[field]) == 64 for field in (
        "source_sha256", "inspection_facts_sha256", "profile_snapshot_sha256", "executable_sha256", "configuration_sha256"
    ))
    assert {page["page_number"] for page in pages} == {1, 2}
    assert {page["rendering_reason"] for page in pages} == {"No Embedded Text", "Layout Review Needed"}
    assert len(body["recognitions"]) == 1
    recognition = body["recognitions"][0]
    recognition_job, recognition_segment = recognition["job"], recognition["segments"][0]
    assert recognition_job["route"] == "Approved local profile — Ephemeral rendered PDF page"
    assert recognition_job["source_sha256"] == sha_bytes(source_bytes)
    assert recognition_job["source_media_type"] == "application/pdf; representation=rendered-page/png"
    assert recognition_job["external_processing"] == 0 and recognition_job["recognition_mode"] == "Handwritten text"
    assert recognition_job["transform"]["source_pdf"] == {"material_id": source["id"], "sha256": sha_bytes(source_bytes), "page_number": 2}
    assert recognition_job["transform"]["rendered_page"]["page_key"] == recognition["page_key"]
    assert recognition_job["transform"]["rendered_page"]["bytes_posture"] == "Ephemeral — Deleted After Validation"
    assert recognition_segment["record_type"] == "Prepared Text — Derived and Unverified"
    assert recognition_segment["review_status"] == "Awaiting Human Review"
    assert recognition_segment["original_text"] == "Meet at 0?30"
    assert recognition_segment["alternatives"] == ["Meet at 0830", "Meet at 0930"]
    assert client.post(f"/api/handwriting-ocr/segments/{recognition_segment['id']}/review", headers=REQUESTER,
                       json={"status": "Confirm Representation", "reason": "Self-review must fail."}).status_code == 409
    reviewed = client.post(f"/api/handwriting-ocr/segments/{recognition_segment['id']}/review", headers=REVIEWER,
                           json={"status": "Correct", "reason": "Compared with the exact fictional PDF page.",
                                 "corrected_text": "Meet at 0830", "limitations": "The page does not establish a date."})
    assert reviewed.status_code == 200 and reviewed.json()["review_status"] == "Correct"
    for page in pages:
        assert page["record_type"] == "Rendered Representation — Not Source Truth"
        assert page["review_status"] == "Awaiting Human Review"
        assert page["source_sha256"] == sha_bytes(source_bytes)
        assert page["rendered_bytes_posture"] == "Ephemeral — Deleted After Validation"
        assert len(page["rendered_sha256"]) == 64
        assert len(page["forward_transform"]) == len(page["inverse_transform"]) == 6
        box = page["crop_box"]
        points = [(box[0], box[1]), (box[2], box[3]), ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)]
        for original in points:
            pixels = apply_transform(page["forward_transform"], *original)
            restored = apply_transform(page["inverse_transform"], *pixels)
            assert abs(restored[0] - original[0]) <= 0.001 and abs(restored[1] - original[1]) <= 0.001

    conn = core.db()
    try:
        assert conn.execute("SELECT COUNT(*) c FROM pdf_render_jobs WHERE tenant_id=?", (1,)).fetchone()["c"] == 1
        assert conn.execute("SELECT COUNT(*) c FROM pdf_rendered_pages WHERE tenant_id=?", (1,)).fetchone()["c"] == 2
        assert conn.execute("SELECT COUNT(*) c FROM handwriting_ocr_jobs WHERE tenant_id=?", (1,)).fetchone()["c"] >= 1
        assert conn.execute("SELECT COUNT(*) c FROM handwriting_ocr_segments WHERE tenant_id=?", (1,)).fetchone()["c"] >= 1
    finally:
        conn.close()
    if os.environ.get("SALUS_DB_BACKEND", "sqlite") == "sqlite":
        conn = core.db()
        try:
            records = core.collect_tenant_records(conn, 1)
        finally:
            conn.close()
        assert records["pdf_render_jobs"] and records["pdf_rendered_pages"]
        assert records["handwriting_ocr_jobs"] and records["handwriting_ocr_segments"] and records["handwriting_ocr_reviews"]
        assert core.validate_records(records, 1) == []
        tampered = copy.deepcopy(records)
        tampered["pdf_rendered_pages"][0]["rendered_sha256"] = "bad"
        assert any("invalid rendered hash" in error for error in core.validate_records(tampered, 1))

    RENDERER.chmod(0o700)
    RENDERER.write_bytes(b"tampered")
    RENDERER.chmod(0o500)
    disabled = client.get("/api/pdf-page-rendering/status", headers=REQUESTER)
    assert disabled.status_code == 200 and disabled.json()["available"] is False
    assert "does not match" in disabled.json()["guidance"]


forward, inverse = _affine([0.0, 0.0, 612.0, 792.0], 90, 1650, 1275)
for original in ((0.0, 0.0), (612.0, 792.0), (306.0, 396.0)):
    restored = apply_transform(inverse, *apply_transform(forward, *original))
    assert abs(restored[0] - original[0]) <= 0.001 and abs(restored[1] - original[1]) <= 0.001

module = (ROOT / "salcapa_pdf_page_rendering.py").read_text(encoding="utf-8")
worker = (ROOT / "tools/salcapa_pdf_render_worker.py").read_text(encoding="utf-8")
for forbidden in ("requests.get(", "urlopen(", "shell=True", "http://", "https://"):
    assert forbidden not in module + worker
for boundary in ("source truth", "authorship", "identity", "finding", "decision", "disclosure authority"):
    assert boundary in module.lower()
print("SALCAPA_PDF_PAGE_RENDERING_SMOKE_PASS", core.DB_BACKEND)
