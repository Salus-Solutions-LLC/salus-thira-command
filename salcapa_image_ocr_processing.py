"""Governed orchestration adapter for isolated JPEG/PNG metadata and OCR extraction."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

import salcapa_material_processing as base
import salcapa_pdf_processing as pdf


PROCESSOR = "SalCAPA Isolated Image Metadata and OCR Extractor"
PROCESSOR_VERSION = "1.0.0"
CONTENT_TYPES = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}
MAX_SOURCE_BYTES = 16 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 8 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 45
WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_image_ocr_worker.py"


def _worker_failure(code: str, detail: str) -> base.ProcessingFailure:
    allowed = {
        "IMAGE_DIMENSION_LIMIT", "IMAGE_FORMAT_MISMATCH", "IMAGE_FRAME_LIMIT", "IMAGE_HEADER_INVALID",
        "IMAGE_METADATA_INVALID", "IMAGE_METADATA_LIMIT", "IMAGE_PARSE_FAILED", "IMAGE_RESOURCE_LIMIT",
        "IMAGE_WORKER_FAILED", "IMAGE_WORKER_INPUT_INVALID", "OCR_FAILED", "OCR_OUTPUT_INVALID",
        "OCR_RESOURCE_LIMIT", "OCR_UNAVAILABLE", "OCR_VERSION_INVALID",
    }
    safe_code = code if code in allowed else "IMAGE_WORKER_FAILED"
    safe_detail = detail if safe_code == code and 1 <= len(detail) <= 1000 else "The isolated image worker could not complete safely. The original remains unchanged."
    return base.ProcessingFailure(safe_code, safe_detail)


def _run_worker(data: bytes, extension: str) -> dict:
    if os.name != "posix" or not WORKER.is_file():
        raise base.ProcessingFailure("IMAGE_WORKER_UNAVAILABLE", "Bounded image processing is unavailable. The original remains available for authorized review.")
    with tempfile.TemporaryDirectory(prefix="salcapa-image-") as directory:
        source = Path(directory) / f"source.{extension}"
        source.write_bytes(data)
        source.chmod(0o400)
        try:
            completed = subprocess.run(
                [sys.executable, "-I", str(WORKER), str(source)], cwd=directory,
                env={"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8"},
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=WORKER_TIMEOUT_SECONDS, check=False, start_new_session=True,
            )
        except subprocess.TimeoutExpired as exc:
            raise base.ProcessingFailure("IMAGE_RESOURCE_LIMIT", "The image exceeded the bounded processing time. The original remains unchanged.") from exc
        except OSError as exc:
            raise base.ProcessingFailure("IMAGE_WORKER_UNAVAILABLE", "The bounded image worker could not start. The original remains available for authorized review.") from exc
        if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
            raise base.ProcessingFailure("IMAGE_RESOURCE_LIMIT", "The image exceeded the bounded processing output. The original remains unchanged.")
        if completed.returncode < 0 and not completed.stdout.strip():
            raise base.ProcessingFailure("IMAGE_RESOURCE_LIMIT", "The image exceeded the bounded processing resources. The original remains unchanged.")
        try:
            payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise base.ProcessingFailure("IMAGE_WORKER_FAILED", "The isolated image worker returned an invalid result. The original remains unchanged.") from exc
        if completed.returncode != 0 or payload.get("ok") is not True:
            raise _worker_failure(str(payload.get("code", "")), str(payload.get("detail", "")))
        return payload


def _decode_image(data: bytes, original_name: str, content_type: str) -> tuple[str, str, bool, str, str]:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in CONTENT_TYPES:
        return _ORIGINAL_DECODER(data, original_name, content_type)
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type != CONTENT_TYPES[extension]:
        raise base.ProcessingFailure("IMAGE_TYPE_MISMATCH", "The image extension and recorded content type do not match. The original remains unchanged for review.")
    if len(data) > MAX_SOURCE_BYTES:
        raise base.ProcessingFailure("IMAGE_SOURCE_LIMIT", "The image exceeds the bounded source-size limit. The original remains unchanged for authorized review.")
    expected = "JPEG" if extension in {"jpg", "jpeg"} else "PNG"
    if (expected == "JPEG" and not data.startswith(b"\xff\xd8\xff")) or (expected == "PNG" and not data.startswith(b"\x89PNG\r\n\x1a\n")):
        raise base.ProcessingFailure("IMAGE_HEADER_INVALID", "The material does not contain the expected JPEG or PNG header. The original remains unchanged for review.")
    payload = _run_worker(data, extension)
    text, facts = payload.get("text"), payload.get("facts")
    if not isinstance(text, str) or not text or len(text) > base.MAX_DERIVED_CHARACTERS or not isinstance(facts, dict):
        raise base.ProcessingFailure("IMAGE_WORKER_FAILED", "The isolated image worker returned an invalid result. The original remains unchanged.")
    if facts.get("processor") != PROCESSOR or facts.get("processor_version") != PROCESSOR_VERSION or facts.get("format") != expected:
        raise base.ProcessingFailure("IMAGE_WORKER_FAILED", "The isolated image worker identity or format could not be verified. The original remains unchanged.")
    width, height, frames = int(facts.get("width", -1)), int(facts.get("height", -1)), int(facts.get("frame_count", -1))
    if width < 1 or height < 1 or frames != 1:
        raise base.ProcessingFailure("IMAGE_WORKER_FAILED", "The isolated image worker returned invalid image facts. The original remains unchanged.")
    language_hash = str(facts.get("english_traineddata_sha256", ""))
    if not re_full_sha256(language_hash):
        raise base.ProcessingFailure("IMAGE_WORKER_FAILED", "The printed-text language data identity could not be verified. The original remains unchanged.")
    method = (
        f"Isolated bounded image metadata and English printed-text extraction by {PROCESSOR} {PROCESSOR_VERSION}; "
        f"format={expected}; dimensions={width}x{height}; frames=1; OCR=tesseract {str(facts.get('tesseract_version', 'unknown'))[:100]}; "
        f"language-data-sha256={language_hash}; fixed oem=1; fixed psm=3; no image interpretation, biometric analysis, object classification, handwriting recognition, geolocation extraction, or external retrieval"
    )
    return text, method, bool(payload.get("truncated")), PROCESSOR, PROCESSOR_VERSION


def re_full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


_ORIGINAL_DECODER = pdf._decode_pdf


def register_salcapa_image_ocr_processing(fastapi_app, core: dict) -> None:
    """Install the image worker chain and register governed orchestration once."""
    base._decode_inert_text = _decode_image
    base.register_salcapa_material_processing(fastapi_app, core)
