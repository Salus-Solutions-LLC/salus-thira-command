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
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
from salcapa_pdf_processing import register_salcapa_pdf_processing  # noqa: E402
from salcapa_pdf_page_rendering import _affine, register_salcapa_pdf_page_rendering  # noqa: E402


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
MEMBER = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Protected Member Contributor"}
OTHER = {**REQUESTER, "X-Salus-Tenant": "2", "X-Salus-User": "Other Tenant Lead"}


with TestClient(core.app) as client:
    status = client.get("/api/pdf-page-rendering/status", headers=REQUESTER)
    assert status.status_code == 200 and status.json()["available"] is True, status.text
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
            {"page_number": 2, "reason": "No Embedded Text"},
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
    finally:
        conn.close()
    if os.environ.get("SALUS_DB_BACKEND", "sqlite") == "sqlite":
        conn = core.db()
        try:
            records = core.collect_tenant_records(conn, 1)
        finally:
            conn.close()
        assert records["pdf_render_jobs"] and records["pdf_rendered_pages"]
        assert core.validate_records(records, 1) == []
        tampered = copy.deepcopy(records)
        tampered["pdf_rendered_pages"][0]["rendered_sha256"] = "bad"
        assert any("invalid rendered hash" in error for error in core.validate_records(tampered, 1))

    RENDERER.write_bytes(b"tampered")
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
