#!/usr/bin/env python3
"""Acceptance checks for bounded, non-executing Office Open XML processing."""

import hashlib
import io
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "office-processing.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

import app as core
from salcapa_office_processing import register_salcapa_office_processing


TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def package(parts: dict[str, str | bytes], compression=zipfile.ZIP_DEFLATED) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=compression) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return stream.getvalue()


def upload(client, headers, name: str, data: bytes, content_type: str) -> dict:
    response = client.post(
        "/api/materials/upload", headers=headers,
        data={"title": f"Fictional {name} source", "material_kind": "Document", "source_origin": "Authorized demonstration submission", "sensitivity": "Restricted"},
        files={"file": (name, data, content_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def process(client, headers, material_id: int):
    return client.post(
        f"/api/materials/{material_id}/safe-text-processing", headers=headers,
        json={"reason": "Prepare a bounded document representation for independent human review."},
    )


def main() -> None:
    register_salcapa_office_processing(core.app, core.__dict__)
    client = TestClient(core.app)
    processor = {"X-Salus-Tenant": "1", "X-Salus-Role": "Assessment Director", "X-Salus-User": "Document Processing Lead"}
    reviewer = {**processor, "X-Salus-User": "Independent Document Reviewer"}
    member = {"X-Salus-Tenant": "1", "X-Salus-Role": "Contributor", "X-Salus-User": "Member Contributor"}

    docx = package({
        "word/document.xml": '<w:document xmlns:w="urn:w"><w:body><w:p><w:r><w:t>Emergency communications annex</w:t></w:r></w:p><w:ins><w:r><w:t>Revision pending authority review</w:t></w:r></w:ins></w:body></w:document>',
        "word/header1.xml": '<w:hdr xmlns:w="urn:w"><w:p><w:r><w:t>Fictional plan</w:t></w:r></w:p></w:hdr>',
        "docProps/core.xml": '<cp:coreProperties xmlns:cp="urn:cp" xmlns:dc="urn:dc"><dc:title>Continuity Plan</dc:title><dc:creator>Recorded source author</dc:creator></cp:coreProperties>',
    })
    source = upload(client, processor, "plan.docx", docx, TYPES["docx"])
    response = process(client, processor, int(source["id"]))
    assert response.status_code == 200, response.text
    derivative_id = int(response.json()["derivative"]["id"])
    detail = client.get(f"/api/material-processing/derivatives/{derivative_id}", headers=reviewer)
    assert detail.status_code == 200, detail.text
    text = detail.json()["content_text"]
    assert "Emergency communications annex" in text and "Revision pending authority review" in text
    assert "Revision markup was present and has not been resolved" in text
    assert "Source-stored document metadata; not independently verified" in text
    assert detail.json()["processor"] == "SalCAPA Safe Office Document Extractor"
    assert detail.json()["source_sha256"] == hashlib.sha256(docx).hexdigest()
    assert client.get(f"/api/material-processing/derivatives/{derivative_id}", headers=member).status_code == 403

    xlsx = package({
        "xl/workbook.xml": '<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Estimate and actual" r:id="rId1"/></sheets></workbook>',
        "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/><Relationship Id="external" Target="https://example.invalid/data" TargetMode="External"/></Relationships>',
        "xl/sharedStrings.xml": '<sst><si><t>Personnel cost</t></si></sst>',
        "xl/worksheets/sheet1.xml": '<worksheet><sheetData><row><c r="A1" t="s"><v>0</v></c><c r="B1"><f>SUM(B2:B3)</f><v>12500</v></c></row></sheetData></worksheet>',
    })
    source = upload(client, processor, "estimate.xlsx", xlsx, TYPES["xlsx"])
    response = process(client, processor, int(source["id"]))
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/material-processing/derivatives/{response.json()['derivative']['id']}", headers=reviewer).json()
    assert "Worksheet: Estimate and actual" in detail["content_text"]
    assert "Personnel cost" in detail["content_text"]
    assert "formula stored; not calculated" in detail["content_text"]
    assert "cached source value: 12500" in detail["content_text"]
    assert "example.invalid" not in detail["content_text"]

    pptx = package({
        "ppt/presentation.xml": '<p:presentation xmlns:p="urn:p" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="rId2"/><p:sldId r:id="rId1"/></p:sldIdLst></p:presentation>',
        "ppt/_rels/presentation.xml.rels": '<Relationships><Relationship Id="rId1" Target="slides/slide1.xml"/><Relationship Id="rId2" Target="slides/slide2.xml"/></Relationships>',
        "ppt/slides/slide1.xml": '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><a:t>First numbered slide</a:t></p:sld>',
        "ppt/slides/slide2.xml": '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><a:t>Presented first</a:t></p:sld>',
        "ppt/notesSlides/notesSlide1.xml": '<p:notes xmlns:p="urn:p" xmlns:a="urn:a"><a:t>Speaker validation cue</a:t></p:notes>',
    })
    source = upload(client, processor, "briefing.pptx", pptx, TYPES["pptx"])
    response = process(client, processor, int(source["id"]))
    assert response.status_code == 200, response.text
    detail = client.get(f"/api/material-processing/derivatives/{response.json()['derivative']['id']}", headers=reviewer).json()
    assert detail["content_text"].index("Presented first") < detail["content_text"].index("First numbered slide")
    assert "Speaker validation cue" in detail["content_text"]
    assert "package-derived approximation" in detail["content_text"]

    unsafe_cases = [
        ("macro.docm", package({"word/document.xml": "<document/>"}), "application/vnd.ms-word.document.macroEnabled.12", "DOCUMENT_ACTIVE_OR_LEGACY_FORMAT"),
        ("traversal.docx", package({"../outside.xml": "x", "word/document.xml": "<document/>"}), TYPES["docx"], "DOCUMENT_PATH_UNSAFE"),
        ("embedded.docx", package({"word/document.xml": "<document/>", "word/embeddings/object.bin": b"object"}), TYPES["docx"], "DOCUMENT_ACTIVE_CONTENT"),
        ("malformed.docx", b"not a zip package", TYPES["docx"], "DOCUMENT_PACKAGE_INVALID"),
        ("mismatch.docx", package({"word/document.xml": "<document/>"}), "application/octet-stream", "DOCUMENT_TYPE_MISMATCH"),
    ]
    for name, data, content_type, failure_code in unsafe_cases:
        source = upload(client, processor, name, data, content_type)
        response = process(client, processor, int(source["id"]))
        assert response.status_code == 422, (name, response.text)
        conn = core.db()
        material = conn.execute("SELECT * FROM materials WHERE id=?", (source["id"],)).fetchone()
        job = conn.execute("SELECT * FROM material_processing_jobs WHERE source_material_id=? ORDER BY id DESC LIMIT 1", (source["id"],)).fetchone()
        assert material["processing_status"] == "Ready for Processing" and material["sha256"] == hashlib.sha256(data).hexdigest()
        assert job["status"] == "Failed" and job["failure_code"] == failure_code
        assert conn.execute("SELECT COUNT(*) c FROM material_derivatives WHERE source_material_id=?", (source["id"],)).fetchone()["c"] == 0
        conn.close()

    search = client.get("/api/material-processing/search?q=Personnel%20cost", headers=reviewer)
    assert search.status_code == 200 and len(search.json()["items"]) == 1, search.text
    assert client.get("/api/material-processing/search?q=Personnel%20cost", headers=member).status_code == 403

    administrator = {**processor, "X-Salus-Role": "System Administrator", "X-Salus-User": "Recovery Custodian"}
    backup = client.post("/api/admin/backups", headers=administrator)
    assert backup.status_code == 200, backup.text
    backup_id = int(backup.json()["id"])
    assert client.post(f"/api/admin/backups/{backup_id}/verify", headers=administrator).json()["ok"]
    assert client.post(f"/api/admin/backups/{backup_id}/dr-validate", headers=administrator).json()["ok"]
    print("SALCAPA_OFFICE_PROCESSING_PASS", core.DB_BACKEND)


if __name__ == "__main__":
    main()
