#!/usr/bin/env python3
"""Acceptance checks for isolated, bounded PDF embedded-text processing."""

import hashlib
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault("SALUS_DB_BACKEND", "sqlite")
os.environ.setdefault("SALUS_DB_PATH", str(Path(WORKSPACE.name) / "pdf-processing.db"))
os.environ.setdefault("SALUS_BACKUP_DIR", str(Path(WORKSPACE.name) / "backups"))
os.environ.setdefault("SALUS_LOCAL_STORAGE_DIR", str(Path(WORKSPACE.name) / "attachments"))
os.environ.setdefault("SALUS_AUTH_MODE", "prototype")
os.environ.setdefault("SALUS_SEED_DEMO", "1")
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject, TextStringObject

import app as core
import salcapa_pdf_processing as pdf
from salcapa_pdf_processing import register_salcapa_pdf_processing


def fictional_pdf(texts: list[str], *, active=False, embedded=False, encrypted=False, empty_annotations=False, annotation=False) -> bytes:
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
        if empty_annotations:
            page[NameObject("/Annots")] = ArrayObject([])
        if annotation:
            note = DictionaryObject({
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Text"),
                NameObject("/Contents"): TextStringObject("Fictional annotation"),
            })
            page[NameObject("/Annots")] = ArrayObject([writer._add_object(note)])
    writer.add_metadata({
        "/Title": "Fictional continuity record",
        "/Author": "Source-recorded demonstration author",
        "/Subject": "Demonstration only",
    })
    if active:
        action = DictionaryObject({
            NameObject("/S"): NameObject("/JavaScript"),
            NameObject("/JS"): TextStringObject("app.alert('not executed')"),
        })
        writer.root_object[NameObject("/OpenAction")] = writer._add_object(action)
    if embedded:
        writer.root_object[NameObject("/Names")] = DictionaryObject({
            NameObject("/EmbeddedFiles"): DictionaryObject({
                NameObject("/Names"): writer._add_object(DictionaryObject()),
            }),
        })
    if encrypted:
        writer.encrypt("fictional-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client, headers, name: str, data: bytes, content_type="application/pdf") -> dict:
    response = client.post(
        "/api/materials/upload", headers=headers,
        data={
            "title": f"Fictional {name} source", "material_kind": "Document",
            "source_origin": "Authorized demonstration submission", "sensitivity": "Restricted",
        },
        files={"file": (name, data, content_type)},
    )
    assert response.status_code == 200, response.text
    return response.json()


def process(client, headers, material_id: int):
    return client.post(
        f"/api/materials/{material_id}/safe-text-processing", headers=headers,
        json={"reason": "Prepare a bounded PDF representation for independent human review."},
    )


def expect_failure(client, headers, name: str, data: bytes, code: str, content_type="application/pdf") -> None:
    source = upload(client, headers, name, data, content_type)
    response = process(client, headers, int(source["id"]))
    assert response.status_code == 422, (name, response.text)
    conn = core.db()
    material = conn.execute("SELECT * FROM materials WHERE id=?", (source["id"],)).fetchone()
    job = conn.execute(
        "SELECT * FROM material_processing_jobs WHERE source_material_id=? ORDER BY id DESC LIMIT 1",
        (source["id"],),
    ).fetchone()
    assert material["processing_status"] == "Ready for Processing"
    assert material["sha256"] == hashlib.sha256(data).hexdigest()
    assert job["status"] == "Failed" and job["failure_code"] == code, dict(job)
    assert conn.execute(
        "SELECT COUNT(*) c FROM material_derivatives WHERE source_material_id=?", (source["id"],)
    ).fetchone()["c"] == 0
    conn.close()


def main() -> None:
    register_salcapa_pdf_processing(core.app, core.__dict__)
    conn = core.db()
    if not conn.execute("SELECT id FROM tenants WHERE id=3").fetchone():
        conn.execute(
            "INSERT INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)",
            (3, "PDF Processing Test Tenant", "pdf-processing-test", "Active", core.now()),
        )
    if not conn.execute("SELECT id FROM assessments WHERE tenant_id=3 LIMIT 1").fetchone():
        conn.execute(
            "INSERT INTO assessments(tenant_id,name,organization,assessment_type,status,purpose,mission,scope,exclusions,executive_sponsor,assessment_director,lead_assessor,target_completion,reassessment_date,classification,scope_locked,version,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (3, "PDF processing recovery fixture", "Fictional Organization", "Enterprise", "Draft", "Recovery validation", "Recovery validation", "PDF processing records", "", "", "", "", "", "", "Standard", 0, 1, core.now(), core.now()),
        )
    conn.commit()
    conn.close()

    client = TestClient(core.app)
    processor = {"X-Salus-Tenant": "3", "X-Salus-Role": "Assessment Director", "X-Salus-User": "PDF Processing Lead"}
    reviewer = {**processor, "X-Salus-User": "Independent PDF Reviewer"}
    member = {"X-Salus-Tenant": "3", "X-Salus-Role": "Contributor", "X-Salus-User": "Member Contributor"}

    source_bytes = fictional_pdf([
        "Emergency communications plan assumption",
        "",
        "Personnel cost estimate requires validation",
    ])
    source_hash = hashlib.sha256(source_bytes).hexdigest()
    temp_root = Path(tempfile.gettempdir())
    before_temp = set(temp_root.glob("salcapa-pdf-*"))
    source = upload(client, processor, "continuity-plan.pdf", source_bytes)
    response = process(client, processor, int(source["id"]))
    assert response.status_code == 200, response.text
    assert set(temp_root.glob("salcapa-pdf-*")) == before_temp
    derivative_id = int(response.json()["derivative"]["id"])
    detail = client.get(f"/api/material-processing/derivatives/{derivative_id}", headers=reviewer)
    assert detail.status_code == 200, detail.text
    record = detail.json()
    text = record["content_text"]
    assert "[PDF page 1" in text and "[PDF page 2" in text and "[PDF page 3" in text
    assert "Emergency communications plan assumption" in text
    assert "Personnel cost estimate requires validation" in text
    assert "Text Not Available — OCR Review Needed" in text
    assert "Source-stored PDF metadata; not independently verified" in text
    assert "Text order and apparent structure are extraction approximations" in text
    assert record["processor"] == pdf.PROCESSOR and record["processor_version"] == pdf.PROCESSOR_VERSION
    assert record["source_sha256"] == source_hash
    assert "no OCR, rendering, attachment access" in record["extraction_method"]
    assert client.get(f"/api/material-processing/derivatives/{derivative_id}", headers=member).status_code == 403

    empty_source = upload(
        client, processor, "empty-annots.pdf",
        fictional_pdf(["Empty annotations are inert."], empty_annotations=True),
    )
    empty_result = process(client, processor, int(empty_source["id"]))
    assert empty_result.status_code == 200, empty_result.text
    empty_detail = client.get(
        f"/api/material-processing/derivatives/{empty_result.json()['derivative']['id']}",
        headers=reviewer,
    )
    assert "Empty annotations are inert." in empty_detail.json()["content_text"]

    same_person = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review", headers=processor,
        json={"status": "Human Reviewed", "reason": "Compare the representation with the fictional source."},
    )
    assert same_person.status_code == 409
    reviewed = client.post(
        f"/api/material-processing/derivatives/{derivative_id}/review", headers=reviewer,
        json={"status": "Human Reviewed", "reason": "Compared the representation with the fictional source; this does not validate source truth."},
    )
    assert reviewed.status_code == 200 and reviewed.json()["review_status"] == "Human Reviewed"
    assert "does not establish the truth" in reviewed.json()["authority_note"]

    search = client.get("/api/material-processing/search?q=Personnel%20cost", headers=reviewer)
    assert search.status_code == 200 and len(search.json()["items"]) == 1, search.text
    assert client.get("/api/material-processing/search?q=Personnel%20cost", headers=member).status_code == 403

    expect_failure(client, processor, "encrypted.pdf", fictional_pdf(["Protected"], encrypted=True), "PDF_ENCRYPTED")
    expect_failure(client, processor, "active.pdf", fictional_pdf(["Action"], active=True), "PDF_ACTIVE_CONTENT")
    expect_failure(client, processor, "annotated.pdf", fictional_pdf(["Action"], annotation=True), "PDF_ACTIVE_CONTENT")
    expect_failure(client, processor, "embedded.pdf", fictional_pdf(["Attachment"], embedded=True), "PDF_ACTIVE_CONTENT")
    expect_failure(client, processor, "malformed.pdf", b"%PDF-1.7\nnot a valid PDF", "PDF_PARSE_FAILED")
    expect_failure(client, processor, "mismatch.pdf", fictional_pdf(["Mismatch"]), "PDF_TYPE_MISMATCH", "application/octet-stream")
    expect_failure(client, processor, "header.pdf", b"not a PDF", "PDF_HEADER_INVALID")
    expect_failure(client, processor, "many-pages.pdf", fictional_pdf([""] * 1001), "PDF_PAGE_LIMIT")

    with patch.object(pdf, "MAX_SOURCE_BYTES", 7):
        try:
            pdf._decode_pdf(b"%PDF-1.7", "limit.pdf", "application/pdf")
            raise AssertionError("source-size control did not fail closed")
        except pdf.base.ProcessingFailure as exc:
            assert exc.code == "PDF_SOURCE_LIMIT"

    with patch.object(pdf.subprocess, "run", side_effect=subprocess.TimeoutExpired(["worker"], 45)):
        try:
            pdf._run_worker(b"%PDF-1.7")
            raise AssertionError("timeout did not fail closed")
        except pdf.base.ProcessingFailure as exc:
            assert exc.code == "PDF_RESOURCE_LIMIT"
    killed = subprocess.CompletedProcess(["worker"], -9, stdout=b"", stderr=b"")
    with patch.object(pdf.subprocess, "run", return_value=killed):
        try:
            pdf._run_worker(b"%PDF-1.7")
            raise AssertionError("resource termination did not fail closed")
        except pdf.base.ProcessingFailure as exc:
            assert exc.code == "PDF_RESOURCE_LIMIT"

    administrator = {**processor, "X-Salus-Role": "System Administrator", "X-Salus-User": "Recovery Custodian"}
    backup = client.post("/api/admin/backups", headers=administrator)
    assert backup.status_code == 200, backup.text
    backup_id = int(backup.json()["id"])
    assert client.post(f"/api/admin/backups/{backup_id}/verify", headers=administrator).json()["ok"]
    assert client.post(f"/api/admin/backups/{backup_id}/dr-validate", headers=administrator).json()["ok"]
    print("SALCAPA_PDF_PROCESSING_PASS", core.DB_BACKEND)


if __name__ == "__main__":
    main()
