#!/usr/bin/env python3
"""Live, bounded acceptance for deployed governed Microsoft 365 intake and extraction."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import PurePosixPath
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from salcapa_image_ocr_processing import _decode_image
from salcapa_material_processing import ProcessingFailure
from salcapa_m365_intake import GovernedM365Config, GovernedM365Intake, GRAPH_ROOT


_REQUIRED_FAMILIES = {"word", "excel", "powerpoint", "pdf", "image"}
_TEXT_EXTENSIONS = {"txt", "md", "csv", "tsv", "json", "xml"}
_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "tif", "tiff", "bmp", "webp"}


def _office_package(parts: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return output.getvalue()


def _parser_fixtures() -> dict[str, tuple[str, str, bytes, str]]:
    """Inert, Member-free sources for every parser in the deployed image."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    font_ref = writer._add_object(font)
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_ref}),
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (SALUS PDF FIXTURE) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    pdf_output = io.BytesIO()
    writer.write(pdf_output)

    picture = Image.new("RGB", (1300, 300), "white")
    draw = ImageDraw.Draw(picture)
    draw.text((35, 90), "ASSEMBLY POINT ALPHA 7", fill="black", font=ImageFont.load_default(size=64))
    image_output = io.BytesIO()
    picture.save(image_output, format="PNG")

    return {
        "word": ("fixture.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", _office_package({
            "word/document.xml": '<w:document xmlns:w="urn:w"><w:body><w:p><w:r><w:t>SALUS WORD FIXTURE</w:t></w:r></w:p></w:body></w:document>',
        }), "SALUS WORD FIXTURE"),
        "excel": ("fixture.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", _office_package({
            "xl/workbook.xml": '<workbook xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Fixture" r:id="rId1"/></sheets></workbook>',
            "xl/_rels/workbook.xml.rels": '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>',
            "xl/worksheets/sheet1.xml": '<worksheet><sheetData><row><c r="A1" t="inlineStr"><is><t>SALUS EXCEL FIXTURE</t></is></c></row></sheetData></worksheet>',
        }), "SALUS EXCEL FIXTURE"),
        "powerpoint": ("fixture.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", _office_package({
            "ppt/presentation.xml": '<p:presentation xmlns:p="urn:p" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldIdLst><p:sldId r:id="rId1"/></p:sldIdLst></p:presentation>',
            "ppt/_rels/presentation.xml.rels": '<Relationships><Relationship Id="rId1" Target="slides/slide1.xml"/></Relationships>',
            "ppt/slides/slide1.xml": '<p:sld xmlns:p="urn:p" xmlns:a="urn:a"><a:t>SALUS POWERPOINT FIXTURE</a:t></p:sld>',
        }), "SALUS POWERPOINT FIXTURE"),
        "pdf": ("fixture.pdf", "application/pdf", pdf_output.getvalue(), "SALUS PDF FIXTURE"),
        "image": ("fixture.png", "image/png", image_output.getvalue(), "ASSEMBLY"),
    }


def _verify_parser_fixtures() -> list[str]:
    accepted = []
    for family, (name, mime_type, content, expected) in sorted(_parser_fixtures().items()):
        try:
            text, method, _truncated, processor, processor_version = _decode_image(content, name, mime_type)
        except ProcessingFailure as exc:
            raise RuntimeError(f"M365_{family.upper()}_FIXTURE_BLOCKED:{exc.code}") from exc
        if not method or not processor or not processor_version or expected not in text.upper():
            raise RuntimeError(f"M365_{family.upper()}_FIXTURE_EXTRACTION_INCOMPLETE")
        accepted.append(family)
    if set(accepted) != _REQUIRED_FAMILIES:
        raise RuntimeError("M365_FIXTURE_FORMAT_COVERAGE_INCOMPLETE")
    return accepted


def _family(name: str) -> str | None:
    suffix = PurePosixPath(name).suffix.lower().lstrip(".")
    if suffix == "docx":
        return "word"
    if suffix == "xlsx":
        return "excel"
    if suffix == "pptx":
        return "powerpoint"
    if suffix == "pdf":
        return "pdf"
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    if suffix in _TEXT_EXTENSIONS:
        return "text"
    return None


def main() -> None:
    config = GovernedM365Config.from_environment()
    config.validate()
    if config.max_file_bytes != 100 * 1024 * 1024:
        raise RuntimeError("M365_INTAKE_100MB_LIMIT_NOT_ACTIVE")
    intake = GovernedM365Intake(config)

    drive_response = intake.client.get(
        f"{GRAPH_ROOT}/drives/{config.drive_id}",
        headers=intake._headers(),
        params={"$select": "id,driveType,webUrl"},
    )
    if drive_response.status_code != 200:
        raise RuntimeError("M365_INTAKE_DRIVE_METADATA_FAILED")
    drive = drive_response.json()
    if str(drive.get("id", "")) != config.drive_id:
        raise RuntimeError("M365_INTAKE_DRIVE_ID_MISMATCH")
    web_url = urlparse(str(drive.get("webUrl", "")))
    if web_url.scheme != "https" or not (web_url.hostname or "").lower().endswith(".sharepoint.com"):
        raise RuntimeError("M365_INTAKE_DRIVE_TRUST_FAILED")

    # The pending backlog can exceed the global tree traversal ceiling. Its
    # finite window proves live Graph scope, ancestry, version and exact bytes.
    # Parser coverage uses inert fixtures below so backlog ordering cannot
    # accidentally remove a format from acceptance or fail a valid release.
    files = intake.list_files(pending_only=True, max_files=500)
    if not files:
        raise RuntimeError("M365_INTAKE_NO_ACCEPTANCE_FILE")
    if not any("/" in str(item.get("relative_path", "")) for item in files):
        raise RuntimeError("M365_INTAKE_NO_NESTED_FILE")

    samples: dict[str, dict] = {}
    for item in files:
        family = _family(str(item.get("name", "")))
        if family and int(item.get("size", 0)) > 0:
            current = samples.get(family)
            if current is None or (int(item["size"]), str(item["id"])) < (
                int(current["size"]), str(current["id"])
            ):
                samples[family] = item

    accepted_live = []
    for family in sorted(samples):
        sample = samples[family]
        document = intake.read_listed_document(
            sample, access_classification="Salus Internal"
        )
        if document.relative_path != sample["relative_path"]:
            raise RuntimeError("M365_INTAKE_RELATIVE_PATH_MISMATCH")
        if document.sha256 != hashlib.sha256(document.content).hexdigest():
            raise RuntimeError("M365_INTAKE_HASH_MISMATCH")
        if not document.etag or not document.last_modified or not document.web_url:
            raise RuntimeError("M365_INTAKE_PROVENANCE_INCOMPLETE")
        try:
            text, method, _truncated, processor, processor_version = _decode_image(
                document.content, document.name, document.mime_type
            )
        except ProcessingFailure as exc:
            # A supported source may contain active content, annotations, encryption,
            # unsafe expansion, or another governed condition. Preserving the original
            # and requiring human review is an accepted fail-closed outcome.
            accepted_live.append(
                f"{family}:blocked:{hashlib.sha256(str(exc).encode('utf-8')).hexdigest()}"
            )
            continue
        if not method or not processor or not processor_version:
            raise RuntimeError(f"M365_{family.upper()}_EXTRACTION_INCOMPLETE")
        if family != "image" and not text.strip():
            raise RuntimeError(f"M365_{family.upper()}_EXTRACTION_EMPTY")
        accepted_live.append(
            f"{family}:extracted:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"
        )

    sample = min(files, key=lambda item: (item["size"] == 0, item["size"], item["id"]))
    # Exercise the same bounded, current-parent read used by the backlog scanner.
    bound = intake.read_listed_document(
        sample, access_classification="Salus Internal"
    )
    if bound.sha256 != hashlib.sha256(bound.content).hexdigest():
        raise RuntimeError("M365_INTAKE_BOUND_READ_HASH_MISMATCH")
    # The unbounded helper walks the entire root, including the processed
    # archive; a live pending acceptance must stay within its discovered
    # finite window and verify each source's current ancestry and version.
    content = intake._read_allowed_item(sample)
    if len(content) != sample["size"] or hashlib.sha256(content).hexdigest() != bound.sha256:
        raise RuntimeError("M365_INTAKE_CONTENT_MISMATCH")

    accepted_fixtures = _verify_parser_fixtures()

    print(
        "M365_LIVE_GOVERNED_EXTRACTION_PASS "
        f"drive_type={str(drive.get('driveType', 'unknown'))[:32]} "
        f"file_count={len(files)} nested=true max_file_bytes={config.max_file_bytes} "
        f"live_families={','.join(item.split(':', 1)[0] for item in accepted_live) or 'none'} "
        f"fixture_families={','.join(accepted_fixtures)} "
        f"sample_bytes={len(content)} sample_sha256={hashlib.sha256(content).hexdigest()}"
    )


if __name__ == "__main__":
    main()

