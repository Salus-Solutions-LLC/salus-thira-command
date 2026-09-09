#!/usr/bin/env python3
"""Isolated, bounded embedded-text extraction for one governed PDF."""

from __future__ import annotations

import json
import os
import re
import resource
import sys
from pathlib import Path


MAX_ADDRESS_SPACE = 512 * 1024 * 1024
MAX_CPU_SECONDS = 30
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_OPEN_FILES = 64
MAX_PAGES = 1_000
MAX_PAGE_CONTENT_BYTES = 16 * 1024 * 1024
MAX_TOTAL_CONTENT_BYTES = 64 * 1024 * 1024
MAX_CHARACTERS = 2_000_000
PROCESSOR = "SalCAPA Isolated PDF Text Extractor"
PROCESSOR_VERSION = "1.0.0"


class WorkerFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _apply_limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE, MAX_ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))
    os.umask(0o077)


def _resolve(value):
    return value.get_object() if hasattr(value, "get_object") else value


def _reject_active_features(reader) -> None:
    root = _resolve(reader.trailer["/Root"])
    rejected_root_keys = {
        "/OpenAction", "/AA", "/AcroForm", "/Collection", "/RichMedia",
    }
    if any(key in root for key in rejected_root_keys):
        raise WorkerFailure(
            "PDF_ACTIVE_CONTENT",
            "The PDF declares an interactive, active, form, portfolio, or rich-media feature and was not processed.",
        )
    names = root.get("/Names")
    if names is not None:
        names = _resolve(names)
        if any(key in names for key in ("/EmbeddedFiles", "/JavaScript")):
            raise WorkerFailure(
                "PDF_ACTIVE_CONTENT",
                "The PDF declares embedded files or document JavaScript and was not processed.",
            )


def _safe_text(value: str) -> str:
    value = value.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    return re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)


def _metadata(reader) -> list[str]:
    try:
        metadata = reader.metadata
    except Exception:
        return []
    if not metadata:
        return []
    fields = (
        ("/Title", "title"), ("/Subject", "subject"), ("/Author", "author-as-recorded"),
        ("/Creator", "creator"), ("/Producer", "producer"), ("/Keywords", "keywords"),
        ("/CreationDate", "creation-time-as-recorded"), ("/ModDate", "modification-time-as-recorded"),
    )
    result = []
    for key, label in fields:
        try:
            value = metadata.get(key)
        except Exception:
            value = None
        if value not in (None, ""):
            result.append(f"{label}: {_safe_text(str(value))[:4000]}")
    return result


def extract(path: Path) -> dict:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(path, strict=True, root_object_recovery_limit=10_000)
    except (PdfReadError, ValueError, TypeError, OSError) as exc:
        raise WorkerFailure(
            "PDF_PARSE_FAILED",
            "The PDF could not be parsed in strict mode. The original remains unchanged for authorized review.",
        ) from exc
    try:
        if reader.is_encrypted:
            raise WorkerFailure(
                "PDF_ENCRYPTED",
                "Encrypted or password-protected PDFs are not processed. The original remains unchanged for authorized review.",
            )
        _reject_active_features(reader)
        page_count = len(reader.pages)
        if page_count > MAX_PAGES:
            raise WorkerFailure(
                "PDF_PAGE_LIMIT",
                "The PDF contains more pages than the bounded processing limit. The original remains unchanged.",
            )
        try:
            labels = list(reader.page_labels)
        except Exception:
            labels = []
        sections: list[str] = []
        decoded_total = 0
        low_text_pages: list[int] = []
        page_facts: list[dict] = []
        truncated = False
        for index, page in enumerate(reader.pages, 1):
            if any(key in page for key in ("/AA", "/Annots", "/RichMedia")):
                raise WorkerFailure(
                    "PDF_ACTIVE_CONTENT",
                    "The PDF contains page actions or annotations and was not processed.",
                )
            try:
                contents = page.get_contents()
                decoded = contents.get_data() if contents is not None else b""
            except MemoryError as exc:
                raise WorkerFailure("PDF_RESOURCE_LIMIT", "The PDF exceeded the bounded processing resources.") from exc
            except Exception as exc:
                raise WorkerFailure(
                    "PDF_CONTENT_STREAM_INVALID",
                    "A PDF page content stream could not be decoded safely. The original remains unchanged.",
                ) from exc
            decoded_size = len(decoded)
            if decoded_size > MAX_PAGE_CONTENT_BYTES:
                raise WorkerFailure(
                    "PDF_PAGE_CONTENT_LIMIT",
                    "A PDF page exceeds the decoded-content processing limit. The original remains unchanged.",
                )
            decoded_total += decoded_size
            if decoded_total > MAX_TOTAL_CONTENT_BYTES:
                raise WorkerFailure(
                    "PDF_CONTENT_LIMIT",
                    "The PDF exceeds the aggregate decoded-content processing limit. The original remains unchanged.",
                )
            try:
                extracted = _safe_text(page.extract_text() or "").strip()
            except MemoryError as exc:
                raise WorkerFailure("PDF_RESOURCE_LIMIT", "The PDF exceeded the bounded processing resources.") from exc
            except Exception as exc:
                raise WorkerFailure(
                    "PDF_TEXT_EXTRACTION_FAILED",
                    "Text could not be extracted safely from a PDF page. The original remains unchanged.",
                ) from exc
            if len(extracted) < 2:
                low_text_pages.append(index)
                extracted = "[Text Not Available — OCR Review Needed]"
            try:
                rotation = int(page.rotation or 0)
            except Exception:
                rotation = 0
            try:
                width = round(float(page.mediabox.width), 2)
                height = round(float(page.mediabox.height), 2)
            except Exception:
                width = height = None
            label = _safe_text(str(labels[index - 1]))[:200] if index <= len(labels) else ""
            heading = f"[PDF page {index}" + (f" | source label: {label}" if label else "") + "]"
            section = heading + "\n" + extracted
            current_length = sum(len(item) for item in sections) + max(0, len(sections) * 2)
            remaining = MAX_CHARACTERS - current_length
            if remaining <= 0:
                truncated = True
                break
            if len(section) > remaining:
                section = section[:remaining]
                truncated = True
            sections.append(section)
            page_facts.append({
                "page": index, "label": label, "rotation": rotation,
                "width_points": width, "height_points": height,
                "decoded_content_bytes": decoded_size, "embedded_text_available": index not in low_text_pages,
            })
            if truncated:
                break
        metadata = _metadata(reader)
        if metadata:
            metadata_section = "[Source-stored PDF metadata; not independently verified]\n" + "\n".join(metadata)
            current = "\n\n".join(sections)
            remaining = MAX_CHARACTERS - len(current) - 2
            if remaining > 0:
                sections.append(metadata_section[:remaining])
                truncated = truncated or len(metadata_section) > remaining
            else:
                truncated = True
        limitations = (
            "[Processing limitations]\n"
            "Text order and apparent structure are extraction approximations. PDF files do not provide a dependable semantic layer. "
            "Extracted text may include hidden, duplicated, out-of-order, or stale OCR-layer text and must be compared with the original. "
            "No OCR, rendering, image interpretation, attachment access, form extraction, signature validation, or external retrieval occurred."
        )
        current = "\n\n".join(sections)
        remaining = MAX_CHARACTERS - len(current) - 2
        if remaining > 0:
            sections.append(limitations[:remaining])
            truncated = truncated or len(limitations) > remaining
        else:
            truncated = True
        return {
            "ok": True,
            "text": "\n\n".join(sections),
            "truncated": truncated,
            "facts": {
                "processor": PROCESSOR, "processor_version": PROCESSOR_VERSION,
                "pdf_header": str(reader.pdf_header), "source_page_count": page_count,
                "pages_represented": len(page_facts), "decoded_content_bytes": decoded_total,
                "low_text_pages": low_text_pages, "page_facts": page_facts,
                "active_feature_inspection": "No rejected declared feature found",
            },
        }
    finally:
        reader.close()


def main() -> None:
    _apply_limits()
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "PDF_WORKER_INPUT_INVALID", "detail": "The PDF worker received invalid input."}))
        raise SystemExit(2)
    try:
        result = extract(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, ensure_ascii=False, separators=(",", ":")))
        raise SystemExit(2)
    except (MemoryError, RecursionError):
        print(json.dumps({"ok": False, "code": "PDF_RESOURCE_LIMIT", "detail": "The PDF exceeded the bounded processing resources."}, separators=(",", ":")))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "PDF_WORKER_FAILED", "detail": "The isolated PDF worker could not complete safely. The original remains unchanged."}, separators=(",", ":")))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
