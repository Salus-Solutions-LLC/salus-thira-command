"""Bounded, non-executing Office Open XML processing for SalCAPA materials."""

from __future__ import annotations

import io
import posixpath
import re
import zipfile
from pathlib import PurePosixPath

from defusedxml import ElementTree as ET

import salcapa_material_processing as base


PROCESSOR = "SalCAPA Safe Office Document Extractor"
PROCESSOR_VERSION = "1.0.0"
MAX_ENTRIES = 2_000
MAX_PART_BYTES = 16 * 1024 * 1024
MAX_EXPANDED_BYTES = 128 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
OOXML_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}
BLOCKED_EXTENSIONS = {"docm", "xlsm", "pptm", "doc", "xls", "ppt"}
ACTIVE_PART_MARKERS = ("/activex/", "/embeddings/", "vbaproject.bin")
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _tag(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def _text_content(element) -> str:
    return "".join(node.text or "" for node in element.iter() if _tag(node) == "t")


def _read_xml(package: zipfile.ZipFile, name: str):
    info = package.getinfo(name)
    if info.file_size > MAX_PART_BYTES:
        raise base.ProcessingFailure("DOCUMENT_PART_LIMIT", "A document part exceeds the safe processing limit. The original remains unchanged.")
    try:
        return ET.fromstring(package.read(name))
    except Exception as exc:
        raise base.ProcessingFailure("DOCUMENT_XML_INVALID", "The document contains XML that could not be parsed safely. The original remains unchanged.") from exc


def _safe_package(data: bytes, extension: str, content_type: str) -> zipfile.ZipFile:
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type != OOXML_TYPES[extension]:
        raise base.ProcessingFailure("DOCUMENT_TYPE_MISMATCH", "The document extension and recorded content type do not match. The original remains unchanged for review.")
    stream = io.BytesIO(data)
    if not zipfile.is_zipfile(stream):
        raise base.ProcessingFailure("DOCUMENT_PACKAGE_INVALID", "The document package is not valid. The original remains unchanged for review.")
    package = zipfile.ZipFile(stream)
    infos = package.infolist()
    if len(infos) > MAX_ENTRIES:
        package.close()
        raise base.ProcessingFailure("DOCUMENT_ENTRY_LIMIT", "The document contains too many package entries for safe processing. The original remains unchanged.")
    expanded = 0
    normalized_names: set[str] = set()
    for info in infos:
        raw = info.filename
        path = PurePosixPath(raw)
        normalized = posixpath.normpath(raw).casefold()
        if "\\" in raw or raw.startswith("/") or ".." in path.parts or normalized in normalized_names:
            package.close()
            raise base.ProcessingFailure("DOCUMENT_PATH_UNSAFE", "The document package contains an unsafe or ambiguous path. The original remains unchanged.")
        normalized_names.add(normalized)
        if info.flag_bits & 0x1:
            package.close()
            raise base.ProcessingFailure("DOCUMENT_ENCRYPTED", "Encrypted document packages are not processed. The original remains unchanged for authorized review.")
        lowered = "/" + normalized
        if any(marker in lowered for marker in ACTIVE_PART_MARKERS):
            package.close()
            raise base.ProcessingFailure("DOCUMENT_ACTIVE_CONTENT", "The document contains embedded or active content and was not processed. The original remains unchanged.")
        expanded += info.file_size
        if info.file_size > MAX_PART_BYTES or expanded > MAX_EXPANDED_BYTES:
            package.close()
            raise base.ProcessingFailure("DOCUMENT_EXPANSION_LIMIT", "The expanded document exceeds the safe processing limit. The original remains unchanged.")
        if info.file_size and (not info.compress_size or info.file_size / info.compress_size > MAX_COMPRESSION_RATIO):
            package.close()
            raise base.ProcessingFailure("DOCUMENT_COMPRESSION_LIMIT", "The document compression ratio exceeds the safe processing limit. The original remains unchanged.")
    return package


def _relationships(package: zipfile.ZipFile, name: str, base_dir: str) -> dict[str, str]:
    if name not in package.namelist():
        return {}
    root = _read_xml(package, name)
    result = {}
    for relationship in root:
        if relationship.attrib.get("TargetMode", "Internal") != "Internal":
            continue
        identifier = relationship.attrib.get("Id", "")
        target = relationship.attrib.get("Target", "")
        candidate = posixpath.normpath(posixpath.join(base_dir, target)).lstrip("/")
        if identifier and ".." not in PurePosixPath(candidate).parts and candidate in package.namelist():
            result[identifier] = candidate
    return result


def _core_properties(package: zipfile.ZipFile) -> list[str]:
    name = "docProps/core.xml"
    if name not in package.namelist():
        return []
    root = _read_xml(package, name)
    allowed = {"title", "subject", "creator", "keywords", "description", "category", "created", "modified", "lastModifiedBy"}
    values = []
    for child in root:
        field = _tag(child)
        value = (child.text or "").strip()
        if field in allowed and value:
            values.append(f"{field}: {value}")
    return values


def _word_text(package: zipfile.ZipFile) -> tuple[str, list[str]]:
    patterns = (
        re.compile(r"^word/document\.xml$"), re.compile(r"^word/header\d+\.xml$"),
        re.compile(r"^word/footer\d+\.xml$"), re.compile(r"^word/(?:footnotes|endnotes|comments)\.xml$"),
    )
    names = sorted(name for name in package.namelist() if any(pattern.match(name) for pattern in patterns))
    if "word/document.xml" not in names:
        raise base.ProcessingFailure("DOCUMENT_MAIN_PART_MISSING", "The Word document has no readable main document part. The original remains unchanged.")
    sections = []
    revision_markup = False
    for name in names:
        root = _read_xml(package, name)
        pieces = []
        for node in root.iter():
            local = _tag(node)
            if local == "t" and node.text:
                pieces.append(node.text)
            elif local in {"tab"}:
                pieces.append("\t")
            elif local in {"br", "cr", "p", "tr"}:
                pieces.append("\n")
            elif local in {"ins", "del", "moveFrom", "moveTo"}:
                revision_markup = True
        text = "".join(pieces).strip()
        if text:
            sections.append(f"[{name}]\n{text}")
    notes = ["Revision markup was present and has not been resolved."] if revision_markup else []
    return "\n\n".join(sections), notes


def _excel_text(package: zipfile.ZipFile) -> tuple[str, list[str]]:
    if "xl/workbook.xml" not in package.namelist():
        raise base.ProcessingFailure("DOCUMENT_MAIN_PART_MISSING", "The Excel workbook has no readable workbook part. The original remains unchanged.")
    shared = []
    if "xl/sharedStrings.xml" in package.namelist():
        for item in _read_xml(package, "xl/sharedStrings.xml"):
            shared.append(_text_content(item))
    rels = _relationships(package, "xl/_rels/workbook.xml.rels", "xl")
    workbook = _read_xml(package, "xl/workbook.xml")
    sheets = []
    for node in workbook.iter():
        if _tag(node) != "sheet":
            continue
        name = node.attrib.get("name", "Worksheet")
        rel_id = node.attrib.get(f"{{{DOC_REL_NS}}}id", "")
        target = rels.get(rel_id)
        if target:
            sheets.append((name, target))
    sections = []
    formula_count = 0
    for sheet_name, target in sheets:
        root = _read_xml(package, target)
        rows = []
        for cell in (node for node in root.iter() if _tag(node) == "c"):
            reference = cell.attrib.get("r", "cell")
            cell_type = cell.attrib.get("t", "")
            formula = next((node.text or "" for node in cell if _tag(node) == "f"), "")
            value = next((node.text or "" for node in cell if _tag(node) == "v"), "")
            inline = next((_text_content(node) for node in cell if _tag(node) == "is"), "")
            if cell_type == "s" and value.isdigit() and int(value) < len(shared):
                value = shared[int(value)]
            elif inline:
                value = inline
            if formula:
                formula_count += 1
                rows.append(f"{reference} [formula stored; not calculated]: {formula}" + (f" | cached source value: {value}" if value else ""))
            elif value:
                rows.append(f"{reference}: {value}")
        sections.append(f"[Worksheet: {sheet_name}]\n" + "\n".join(rows))
    notes = [f"{formula_count} formula cell(s) were not calculated; any cached values came from the source package."] if formula_count else []
    return "\n\n".join(sections), notes


def _powerpoint_text(package: zipfile.ZipFile) -> tuple[str, list[str]]:
    if "ppt/presentation.xml" not in package.namelist():
        raise base.ProcessingFailure("DOCUMENT_MAIN_PART_MISSING", "The PowerPoint file has no readable presentation part. The original remains unchanged.")
    rels = _relationships(package, "ppt/_rels/presentation.xml.rels", "ppt")
    presentation = _read_xml(package, "ppt/presentation.xml")
    ordered = []
    for node in presentation.iter():
        if _tag(node) == "sldId":
            target = rels.get(node.attrib.get(f"{{{DOC_REL_NS}}}id", ""))
            if target:
                ordered.append(target)
    sections = []
    for index, target in enumerate(ordered, 1):
        text = _text_content(_read_xml(package, target)).strip()
        sections.append(f"[Slide {index}]\n{text}")
    note_names = sorted(name for name in package.namelist() if re.match(r"^ppt/notesSlides/notesSlide\d+\.xml$", name))
    for index, name in enumerate(note_names, 1):
        text = _text_content(_read_xml(package, name)).strip()
        if text:
            sections.append(f"[Speaker notes {index}]\n{text}")
    return "\n\n".join(sections), ["Text order is a package-derived approximation and requires human review."]


def _decode_office(data: bytes, original_name: str, content_type: str) -> tuple[str, str, bool, str, str]:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension in BLOCKED_EXTENSIONS:
        raise base.ProcessingFailure("DOCUMENT_ACTIVE_OR_LEGACY_FORMAT", "Macro-enabled and legacy binary Office files are not processed. The original remains unchanged for authorized review.")
    if extension not in OOXML_TYPES:
        return _ORIGINAL_DECODER(data, original_name, content_type)
    package = _safe_package(data, extension, content_type)
    try:
        if extension == "docx":
            text, notes = _word_text(package)
            format_name = "Word"
        elif extension == "xlsx":
            text, notes = _excel_text(package)
            format_name = "Excel"
        else:
            text, notes = _powerpoint_text(package)
            format_name = "PowerPoint"
        metadata = _core_properties(package)
    finally:
        package.close()
    if not text.strip() and not metadata:
        raise base.ProcessingFailure("DOCUMENT_TEXT_EMPTY", "No supported readable text or metadata was found. The original remains unchanged for review.")
    sections = [text.strip()]
    if metadata:
        sections.append("[Source-stored document metadata; not independently verified]\n" + "\n".join(metadata))
    if notes:
        sections.append("[Processing limitations]\n" + "\n".join(notes))
    result = "\n\n".join(section for section in sections if section)
    truncated = len(result) > base.MAX_DERIVED_CHARACTERS
    if truncated:
        result = result[:base.MAX_DERIVED_CHARACTERS]
    method = f"Non-executing {format_name} Open XML text and limited-metadata extraction by {PROCESSOR} {PROCESSOR_VERSION}"
    return result, method, truncated, PROCESSOR, PROCESSOR_VERSION


_ORIGINAL_DECODER = base._decode_inert_text


def register_salcapa_office_processing(fastapi_app, core: dict) -> None:
    """Install the bounded worker, then register the governed v3.101 orchestration."""
    base._decode_inert_text = _decode_office
    base.register_salcapa_material_processing(fastapi_app, core)
