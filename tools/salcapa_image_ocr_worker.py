#!/usr/bin/env python3
"""Isolated, bounded metadata and printed-text extraction for JPEG and PNG."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile
import warnings


MAX_ADDRESS_SPACE = 512 * 1024 * 1024
MAX_CPU_SECONDS = 30
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_OPEN_FILES = 64
MAX_DIMENSION = 8_000
MAX_PIXELS = 16_000_000
MAX_METADATA_BYTES = 1 * 1024 * 1024
MAX_CHARACTERS = 500_000
MAX_OCR_OUTPUT_BYTES = 8 * 1024 * 1024
OCR_TIMEOUT_SECONDS = 30
PROCESSOR = "SalCAPA Isolated Image Metadata and OCR Extractor"
PROCESSOR_VERSION = "1.0.0"
TESSERACT = Path("/usr/bin/tesseract")
TESSDATA = Path("/usr/share/tesseract-ocr/5/tessdata")
ENG_DATA = TESSDATA / "eng.traineddata"
EXIF_FIELDS = {
    306: "capture-time", 271: "camera-make", 272: "camera-model",
    305: "software", 274: "orientation", 282: "x-resolution", 283: "y-resolution",
}


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


def _safe_value(value: object) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value)).strip()
    return text[:1024]


def _metadata(image) -> tuple[list[str], dict, int]:
    entries: list[str] = []
    facts: dict[str, object] = {"gps_metadata_present": False}
    size = sum(len(str(key).encode()) + len(repr(value).encode()) for key, value in image.info.items())
    try:
        exif = image.getexif()
        raw = exif.tobytes() if exif else b""
    except Exception as exc:
        raise WorkerFailure("IMAGE_METADATA_INVALID", "The image metadata could not be read safely. The original remains unchanged.") from exc
    size += len(raw)
    if size > MAX_METADATA_BYTES:
        raise WorkerFailure("IMAGE_METADATA_LIMIT", "The image metadata exceeds the bounded processing limit. The original remains unchanged.")
    if exif:
        facts["gps_metadata_present"] = 34853 in exif
        for tag, label in EXIF_FIELDS.items():
            if tag in exif:
                entries.append(f"{label}: {_safe_value(exif.get(tag))}")
    facts["selected_metadata_fields"] = len(entries)
    facts["metadata_bytes_inspected"] = size
    facts["metadata_present"] = bool(image.info or exif)
    return entries, facts, size


def _tesseract_version() -> str:
    if not TESSERACT.is_file() or not os.access(TESSERACT, os.X_OK) or not ENG_DATA.is_file():
        raise WorkerFailure("OCR_UNAVAILABLE", "The bounded English printed-text worker is unavailable. The original remains available for authorized review.")
    try:
        result = subprocess.run(
            [str(TESSERACT), "--version"], stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=5, check=False,
            env={"LC_ALL": "C.UTF-8", "OMP_THREAD_LIMIT": "1", "TESSDATA_PREFIX": str(TESSDATA)},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerFailure("OCR_UNAVAILABLE", "The bounded English printed-text worker is unavailable. The original remains available for authorized review.") from exc
    line = result.stdout.decode("utf-8", errors="replace").splitlines()[0] if result.stdout else ""
    if result.returncode != 0 or not re.fullmatch(r"tesseract 5\.[0-9]+\.[0-9]+(?:[^\r\n]*)?", line):
        raise WorkerFailure("OCR_VERSION_INVALID", "The printed-text worker identity could not be verified. The original remains unchanged.")
    return line.removeprefix("tesseract ")[:100]


def _ocr(clean_path: Path, width: int, height: int) -> tuple[str, dict]:
    version = _tesseract_version()
    language_hash = hashlib.sha256(ENG_DATA.read_bytes()).hexdigest()
    env = {
        "HOME": str(clean_path.parent), "TMPDIR": str(clean_path.parent), "LC_ALL": "C.UTF-8",
        "OMP_THREAD_LIMIT": "1", "TESSDATA_PREFIX": str(TESSDATA),
    }
    try:
        result = subprocess.run(
            [str(TESSERACT), str(clean_path), "stdout", "-l", "eng", "--oem", "1", "--psm", "3", "tsv", "quiet"],
            cwd=clean_path.parent, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=OCR_TIMEOUT_SECONDS, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkerFailure("OCR_RESOURCE_LIMIT", "Printed-text recognition exceeded the bounded processing time. The original remains unchanged.") from exc
    except OSError as exc:
        raise WorkerFailure("OCR_UNAVAILABLE", "The bounded English printed-text worker could not start. The original remains available for authorized review.") from exc
    if len(result.stdout) > MAX_OCR_OUTPUT_BYTES:
        raise WorkerFailure("OCR_RESOURCE_LIMIT", "Printed-text recognition exceeded the bounded output limit. The original remains unchanged.")
    if result.returncode != 0:
        raise WorkerFailure("OCR_FAILED", "Printed text could not be recognized safely. The original remains unchanged for authorized review.")
    try:
        decoded = result.stdout.decode("utf-8", errors="strict")
        rows = list(csv.DictReader(io.StringIO(decoded), delimiter="\t"))
    except (UnicodeDecodeError, csv.Error) as exc:
        raise WorkerFailure("OCR_OUTPUT_INVALID", "The printed-text worker returned an invalid result. The original remains unchanged.") from exc
    words: list[tuple[tuple[int, int, int, int], str]] = []
    for row in rows:
        if row.get("level") != "5" or not (row.get("text") or "").strip():
            continue
        try:
            key = tuple(int(row[name]) for name in ("page_num", "block_num", "par_num", "line_num"))
            left, top, box_width, box_height = (int(row[name]) for name in ("left", "top", "width", "height"))
            confidence = float(row["conf"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The printed-text worker returned invalid position or confidence data.") from exc
        if min(left, top, box_width, box_height) < 0 or left + box_width > width or top + box_height > height or not -1 <= confidence <= 100:
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The printed-text worker returned out-of-bounds position or confidence data.")
        words.append((key, re.sub(r"[\x00-\x1f\x7f]", " ", row["text"]).strip()))
    lines: list[str] = []
    current = None
    parts: list[str] = []
    for key, word in words:
        if current is not None and key != current:
            lines.append(" ".join(parts))
            parts = []
        current = key
        parts.append(word)
    if parts:
        lines.append(" ".join(parts))
    text = "\n".join(lines)
    truncated = len(text) > MAX_CHARACTERS
    return text[:MAX_CHARACTERS], {
        "tesseract_version": version, "english_traineddata_sha256": language_hash,
        "ocr_language": "eng", "ocr_engine_mode": 1, "ocr_page_segmentation_mode": 3,
        "recognized_word_count": len(words), "ocr_text_truncated": truncated,
    }


def extract(path: Path) -> dict:
    from PIL import Image, ImageOps
    from PIL.Image import DecompressionBombError, DecompressionBombWarning

    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    warnings.simplefilter("error", DecompressionBombWarning)
    header = path.read_bytes()[:16]
    expected = "JPEG" if header.startswith(b"\xff\xd8\xff") else "PNG" if header.startswith(b"\x89PNG\r\n\x1a\n") else None
    if expected is None:
        raise WorkerFailure("IMAGE_HEADER_INVALID", "The material does not contain a supported JPEG or PNG header. The original remains unchanged.")
    try:
        with Image.open(path, formats=[expected]) as check:
            check.verify()
        with Image.open(path, formats=[expected]) as image:
            if image.format != expected:
                raise WorkerFailure("IMAGE_FORMAT_MISMATCH", "The recorded image format does not match its contents. The original remains unchanged.")
            frames = int(getattr(image, "n_frames", 1))
            if frames != 1 or bool(getattr(image, "is_animated", False)):
                raise WorkerFailure("IMAGE_FRAME_LIMIT", "Animated or multi-frame images are not processed. The original remains unchanged.")
            width, height = image.size
            if width < 1 or height < 1 or width > MAX_DIMENSION or height > MAX_DIMENSION or width * height > MAX_PIXELS:
                raise WorkerFailure("IMAGE_DIMENSION_LIMIT", "The image dimensions exceed the bounded processing limit. The original remains unchanged.")
            metadata, meta_facts, _ = _metadata(image)
            orientation = image.getexif().get(274, 1)
            transformed = ImageOps.exif_transpose(image)
            transformed.load()
            clean = transformed.convert("L")
            clean_width, clean_height = clean.size
            with tempfile.TemporaryDirectory(prefix="salcapa-ocr-") as directory:
                clean_path = Path(directory) / "normalized.png"
                clean.save(clean_path, "PNG", optimize=False)
                ocr_text, ocr_facts = _ocr(clean_path, clean_width, clean_height)
    except WorkerFailure:
        raise
    except (DecompressionBombError, DecompressionBombWarning, MemoryError) as exc:
        raise WorkerFailure("IMAGE_RESOURCE_LIMIT", "The image exceeded the bounded processing resources. The original remains unchanged.") from exc
    except Exception as exc:
        raise WorkerFailure("IMAGE_PARSE_FAILED", "The image could not be decoded safely. The original remains unchanged for authorized review.") from exc
    sections = ["[Recognized English printed text — Derived — Unverified]", ocr_text or "[Printed text not recognized]"]
    if metadata:
        sections += ["", "[Selected source-stored metadata — not independently verified]", *metadata]
    sections += ["", "[Processing limitations]", "Recognized text and reading order are approximations requiring comparison with the original. No image interpretation, face or biometric analysis, object classification, handwriting recognition, geolocation extraction, external retrieval, or human review occurred."]
    return {"ok": True, "text": "\n".join(sections), "truncated": bool(ocr_facts["ocr_text_truncated"]), "facts": {
        "processor": PROCESSOR, "processor_version": PROCESSOR_VERSION, "format": expected,
        "width": width, "height": height, "color_mode": image.mode, "frame_count": frames,
        "orientation_applied": orientation not in (None, 1, "1"), **meta_facts, **ocr_facts,
    }}


def main() -> None:
    _apply_limits()
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "IMAGE_WORKER_INPUT_INVALID", "detail": "The image worker received invalid input."}))
        raise SystemExit(2)
    try:
        result = extract(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":")))
        raise SystemExit(2)
    except (MemoryError, RecursionError):
        print(json.dumps({"ok": False, "code": "IMAGE_RESOURCE_LIMIT", "detail": "The image exceeded the bounded processing resources."}, separators=(",", ":")))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "IMAGE_WORKER_FAILED", "detail": "The isolated image worker could not complete safely. The original remains unchanged."}, separators=(",", ":")))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
