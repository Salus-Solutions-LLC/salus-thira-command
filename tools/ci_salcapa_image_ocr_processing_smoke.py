#!/usr/bin/env python3
"""Governance smoke checks for bounded JPEG/PNG metadata and OCR processing."""

from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.chdir(ROOT)
os.environ.update({
    "SALUS_AUTH_MODE": "prototype", "SALUS_SEED_DEMO": "1",
    "SALUS_DB_BACKEND": "sqlite", "SALUS_DB_PATH": str(Path(WORKSPACE.name) / "image-ocr.db"),
    "SALUS_LOCAL_STORAGE_DIR": str(Path(WORKSPACE.name) / "attachments"),
    "SALUS_BACKUP_DIR": str(Path(WORKSPACE.name) / "backups"),
})
sys.path.insert(0, str(ROOT))

import app as core  # noqa: E402
import salcapa_image_ocr_processing as image_processing  # noqa: E402
from salcapa_image_ocr_processing import register_salcapa_image_ocr_processing  # noqa: E402

register_salcapa_image_ocr_processing(core.app, core.__dict__)


def make_image(format_name: str, *, animated: bool = False) -> bytes:
    image = Image.new("RGB", (1300, 300), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=64)
    draw.text((35, 90), "ASSEMBLY POINT ALPHA 7", fill="black", font=font)
    exif = Image.Exif()
    exif[271] = "Demonstration Camera"
    exif[272] = "Model 7"
    output = io.BytesIO()
    if animated:
        second = Image.new("RGB", image.size, "white")
        image.save(output, format="PNG", save_all=True, append_images=[second], duration=100, loop=0)
    else:
        image.save(output, format=format_name, exif=exif)
    return output.getvalue()


def upload(client: TestClient, name: str, content_type: str, data: bytes):
    response = client.post(
        "/api/materials/upload", headers=HEADERS,
        files={"file": (name, data, content_type)},
        data={"title": f"Fictional {name}", "material_kind": "Image", "source_origin": "Authorized demonstration submission", "sensitivity": "Restricted"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def process(client: TestClient, source: dict):
    return client.post(
        f"/api/materials/{source['id']}/safe-text-processing", headers=HEADERS,
        json={"reason": "Prepare a bounded image representation for independent human review."},
    )


def expect_failure(client: TestClient, name: str, content_type: str, data: bytes, code: str) -> None:
    source = upload(client, name, content_type, data)
    response = process(client, source)
    assert response.status_code == 422, response.text
    conn = core.db()
    job = conn.execute("SELECT * FROM material_processing_jobs WHERE source_material_id=? ORDER BY id DESC LIMIT 1", (source["id"],)).fetchone()
    conn.close()
    assert job["status"] == "Failed" and job["failure_code"] == code, dict(job)


conn = core.db()
if not conn.execute("SELECT id FROM tenants WHERE id=4").fetchone():
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)", (4, "Image OCR Test Tenant", "image-ocr-test", "Active", core.now()))
conn.commit()
conn.close()
HEADERS = {"X-Salus-User": "Image Processing Lead", "X-Salus-Tenant": "4", "X-Salus-Role": "Assessment Director"}

with TestClient(core.app) as client:
    for name, content_type, data in (
        ("assembly.png", "image/png", make_image("PNG")),
        ("assembly.jpeg", "image/jpeg", make_image("JPEG")),
    ):
        response = process(client, upload(client, name, content_type, data))
        assert response.status_code == 200, response.text
        record = response.json()["derivative"]
        assert record["review_status"] == "Awaiting Human Review"
        assert record["confidence_status"] == "Derived — Unverified"
        assert "ASSEMBLY" in record["content_preview"].upper()
        assert "no image interpretation" in record["extraction_method"]
        assert "language-data-sha256=" in record["extraction_method"]
        assert record["processor"] == "SalCAPA Isolated Image Metadata and OCR Extractor"
        assert record["source_sha256"]

    expect_failure(client, "wrong.png", "image/jpeg", make_image("PNG"), "IMAGE_TYPE_MISMATCH")
    expect_failure(client, "false.png", "image/png", b"not an image", "IMAGE_HEADER_INVALID")
    expect_failure(client, "animated.png", "image/png", make_image("PNG", animated=True), "IMAGE_FRAME_LIMIT")

    original_limit = image_processing.MAX_SOURCE_BYTES
    image_processing.MAX_SOURCE_BYTES = 8
    try:
        expect_failure(client, "large.png", "image/png", make_image("PNG"), "IMAGE_SOURCE_LIMIT")
    finally:
        image_processing.MAX_SOURCE_BYTES = original_limit

print("SALCAPA_IMAGE_OCR_PROCESSING_SMOKE_PASS")
