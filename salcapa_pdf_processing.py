"""Governed orchestration adapter for isolated, bounded PDF text extraction."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import salcapa_material_processing as base
import salcapa_office_processing as office


PROCESSOR = "SalCAPA Isolated PDF Text Extractor"
PROCESSOR_VERSION = "1.0.0"
PDF_CONTENT_TYPE = "application/pdf"
MAX_SOURCE_BYTES = 64 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 16 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 45
WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_pdf_worker.py"


def _worker_failure(code: str, detail: str) -> base.ProcessingFailure:
    allowed = {
        "PDF_ACTIVE_CONTENT", "PDF_CONTENT_LIMIT", "PDF_CONTENT_STREAM_INVALID",
        "PDF_ENCRYPTED", "PDF_PAGE_CONTENT_LIMIT", "PDF_PAGE_LIMIT",
        "PDF_PARSE_FAILED", "PDF_RESOURCE_LIMIT", "PDF_TEXT_EXTRACTION_FAILED",
        "PDF_WORKER_FAILED", "PDF_WORKER_INPUT_INVALID",
    }
    safe_code = code if code in allowed else "PDF_WORKER_FAILED"
    safe_detail = detail if safe_code == code and 1 <= len(detail) <= 1000 else (
        "The isolated PDF worker could not complete safely. The original remains unchanged."
    )
    return base.ProcessingFailure(safe_code, safe_detail)


def _run_worker(data: bytes) -> dict:
    if os.name != "posix":
        raise base.ProcessingFailure(
            "PDF_WORKER_UNAVAILABLE",
            "Bounded PDF processing is unavailable in this environment. The original remains available for authorized review.",
        )
    if not WORKER.is_file():
        raise base.ProcessingFailure(
            "PDF_WORKER_UNAVAILABLE",
            "The bounded PDF worker is unavailable. The original remains available for authorized review.",
        )
    with tempfile.TemporaryDirectory(prefix="salcapa-pdf-") as directory:
        source = Path(directory) / "source.pdf"
        source.write_bytes(data)
        source.chmod(0o400)
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(WORKER), str(source)],
                cwd=directory,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8"},
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=WORKER_TIMEOUT_SECONDS,
                check=False,
                start_new_session=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise base.ProcessingFailure(
                "PDF_RESOURCE_LIMIT",
                "The PDF exceeded the bounded processing time. The original remains unchanged for authorized review.",
            ) from exc
        except OSError as exc:
            raise base.ProcessingFailure(
                "PDF_WORKER_UNAVAILABLE",
                "The bounded PDF worker could not start. The original remains available for authorized review.",
            ) from exc
        if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
            raise base.ProcessingFailure(
                "PDF_RESOURCE_LIMIT",
                "The PDF exceeded the bounded processing output. The original remains unchanged for authorized review.",
            )
        if completed.returncode < 0 and not completed.stdout.strip():
            raise base.ProcessingFailure(
                "PDF_RESOURCE_LIMIT",
                "The PDF exceeded the bounded processing resources. The original remains unchanged.",
            )
        try:
            payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise base.ProcessingFailure(
                "PDF_WORKER_FAILED",
                "The isolated PDF worker returned an invalid result. The original remains unchanged.",
            ) from exc
        if completed.returncode != 0 or payload.get("ok") is not True:
            if completed.returncode < 0 and not payload.get("code"):
                raise base.ProcessingFailure(
                    "PDF_RESOURCE_LIMIT",
                    "The PDF exceeded the bounded processing resources. The original remains unchanged.",
                )
            raise _worker_failure(str(payload.get("code", "")), str(payload.get("detail", "")))
        return payload


def _decode_pdf(data: bytes, original_name: str, content_type: str) -> tuple[str, str, bool, str, str]:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if extension != "pdf":
        return _ORIGINAL_DECODER(data, original_name, content_type)
    if normalized_type != PDF_CONTENT_TYPE:
        raise base.ProcessingFailure(
            "PDF_TYPE_MISMATCH",
            "The PDF extension and recorded content type do not match. The original remains unchanged for review.",
        )
    if len(data) > MAX_SOURCE_BYTES:
        raise base.ProcessingFailure(
            "PDF_SOURCE_LIMIT",
            "The PDF exceeds the bounded source-size limit. The original remains unchanged for authorized review.",
        )
    if not data.startswith(b"%PDF-"):
        raise base.ProcessingFailure(
            "PDF_HEADER_INVALID",
            "The material does not contain a supported PDF header. The original remains unchanged for review.",
        )
    payload = _run_worker(data)
    text = payload.get("text")
    facts = payload.get("facts")
    if not isinstance(text, str) or not text or len(text) > base.MAX_DERIVED_CHARACTERS:
        raise base.ProcessingFailure(
            "PDF_WORKER_FAILED",
            "The isolated PDF worker returned an invalid text result. The original remains unchanged.",
        )
    if not isinstance(facts, dict):
        raise base.ProcessingFailure(
            "PDF_WORKER_FAILED",
            "The isolated PDF worker returned invalid processing facts. The original remains unchanged.",
        )
    if facts.get("processor") != PROCESSOR or facts.get("processor_version") != PROCESSOR_VERSION:
        raise base.ProcessingFailure(
            "PDF_WORKER_FAILED",
            "The isolated PDF worker identity could not be verified. The original remains unchanged.",
        )
    page_count = int(facts.get("source_page_count", -1))
    represented = int(facts.get("pages_represented", -1))
    if page_count < 0 or represented < 0 or represented > page_count:
        raise base.ProcessingFailure(
            "PDF_WORKER_FAILED",
            "The isolated PDF worker returned invalid page facts. The original remains unchanged.",
        )
    low_text = facts.get("low_text_pages", [])
    if not isinstance(low_text, list) or len(low_text) > page_count:
        raise base.ProcessingFailure(
            "PDF_WORKER_FAILED",
            "The isolated PDF worker returned invalid text-availability facts. The original remains unchanged.",
        )
    method = (
        f"Isolated strict PDF embedded-text extraction by {PROCESSOR} {PROCESSOR_VERSION}; "
        f"header={str(facts.get('pdf_header', 'unknown'))[:20]}; source_pages={page_count}; "
        f"pages_represented={represented}; low_text_pages={len(low_text)}; "
        f"decoded_content_bytes={int(facts.get('decoded_content_bytes', 0))}; "
        "no OCR, rendering, attachment access, active-content execution, or external retrieval"
    )
    return text, method, bool(payload.get("truncated")), PROCESSOR, PROCESSOR_VERSION


_ORIGINAL_DECODER = office._decode_office


def register_salcapa_pdf_processing(fastapi_app, core: dict) -> None:
    """Install the PDF worker chain and register the governed orchestration once."""
    base._decode_inert_text = _decode_pdf
    base.register_salcapa_material_processing(fastapi_app, core)
