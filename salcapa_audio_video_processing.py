"""Governed orchestration adapter for isolated audio and video transcription."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading

import salcapa_image_ocr_processing as image
import salcapa_material_processing as base


PROCESSOR = "SalCAPA Isolated Audio and Video Transcript Preparer"
PROCESSOR_VERSION = "1.0.0"
CONTENT_TYPES = {
    "wav": {"audio/wav", "audio/x-wav", "audio/vnd.wave"},
    "mp3": {"audio/mpeg"},
    "mp4": {"video/mp4"},
}
MAX_SOURCE_BYTES = 128 * 1024 * 1024
MAX_WORKER_OUTPUT_BYTES = 8 * 1024 * 1024
WORKER_TIMEOUT_SECONDS = 20 * 60
WORKER = Path(__file__).resolve().parent / "tools" / "salcapa_audio_video_worker.py"
_CAPACITY = threading.BoundedSemaphore(1)


def _worker_failure(code: str, detail: str) -> base.ProcessingFailure:
    allowed = {
        "MEDIA_DECODE_FAILED", "MEDIA_DURATION_LIMIT", "MEDIA_FORMAT_MISMATCH",
        "MEDIA_HEADER_INVALID", "MEDIA_OUTPUT_INVALID", "MEDIA_PROBE_FAILED",
        "MEDIA_RESOURCE_LIMIT", "MEDIA_STREAM_INVALID", "MEDIA_STREAM_LIMIT",
        "MEDIA_WORKER_FAILED", "MEDIA_WORKER_INPUT_INVALID", "TRANSCRIPT_OUTPUT_INVALID",
        "TRANSCRIPTION_FAILED", "TRANSCRIPTION_MODEL_INVALID", "TRANSCRIPTION_UNAVAILABLE",
    }
    safe_code = code if code in allowed else "MEDIA_WORKER_FAILED"
    safe_detail = detail if safe_code == code and 1 <= len(detail) <= 1000 else (
        "The isolated transcription worker could not complete safely. The original remains unchanged."
    )
    return base.ProcessingFailure(safe_code, safe_detail)


def _header_matches(data: bytes, extension: str) -> bool:
    if extension == "wav":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    if extension == "mp3":
        return data.startswith(b"ID3") or (
            len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0
        )
    return len(data) >= 12 and data[4:8] == b"ftyp"


def _run_worker(data: bytes, extension: str, *, timeout_seconds: int = WORKER_TIMEOUT_SECONDS) -> dict:
    if os.name != "posix" or not WORKER.is_file():
        raise base.ProcessingFailure(
            "TRANSCRIPTION_UNAVAILABLE",
            "Bounded transcription is unavailable. The original remains available for authorized manual review.",
        )
    if not _CAPACITY.acquire(blocking=False):
        raise base.ProcessingFailure(
            "TRANSCRIPTION_CAPACITY_UNAVAILABLE",
            "Transcription capacity is currently unavailable. Try later or review the original recording manually.",
        )
    try:
        with tempfile.TemporaryDirectory(prefix="salcapa-media-") as directory:
            source = Path(directory) / f"source.{extension}"
            source.write_bytes(data)
            source.chmod(0o400)
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(WORKER), str(source)], cwd=directory,
                    env={"PYTHONIOENCODING": "utf-8", "PYTHONHASHSEED": "0", "LC_ALL": "C.UTF-8"},
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=timeout_seconds, check=False, start_new_session=True,
                )
            except subprocess.TimeoutExpired as exc:
                raise base.ProcessingFailure(
                    "MEDIA_RESOURCE_LIMIT",
                    "The recording exceeded the bounded processing time. The original remains unchanged.",
                ) from exc
            except OSError as exc:
                raise base.ProcessingFailure(
                    "TRANSCRIPTION_UNAVAILABLE",
                    "The bounded transcription worker could not start. Manual review remains available.",
                ) from exc
            if len(completed.stdout) > MAX_WORKER_OUTPUT_BYTES:
                raise base.ProcessingFailure(
                    "MEDIA_RESOURCE_LIMIT",
                    "The recording exceeded the bounded processing output. The original remains unchanged.",
                )
            if completed.returncode < 0 and not completed.stdout.strip():
                raise base.ProcessingFailure(
                    "MEDIA_RESOURCE_LIMIT",
                    "The recording exceeded the bounded processing resources. The original remains unchanged.",
                )
            try:
                payload = json.loads(completed.stdout.decode("utf-8", errors="strict"))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
                raise base.ProcessingFailure(
                    "MEDIA_WORKER_FAILED",
                    "The isolated transcription worker returned an invalid result. The original remains unchanged.",
                ) from exc
            if completed.returncode != 0 or payload.get("ok") is not True:
                raise _worker_failure(str(payload.get("code", "")), str(payload.get("detail", "")))
            return payload
    finally:
        _CAPACITY.release()


def _decode_media(data: bytes, original_name: str, content_type: str, *, worker_timeout_seconds: int = WORKER_TIMEOUT_SECONDS) -> tuple[str, str, bool, str, str]:
    extension = original_name.rsplit(".", 1)[-1].lower() if "." in original_name else ""
    if extension not in CONTENT_TYPES:
        return _ORIGINAL_DECODER(data, original_name, content_type)
    normalized_type = content_type.split(";", 1)[0].strip().lower()
    if normalized_type not in CONTENT_TYPES[extension]:
        raise base.ProcessingFailure(
            "MEDIA_FORMAT_MISMATCH",
            "The recording extension and content type do not match. The original remains unchanged for review.",
        )
    if len(data) > MAX_SOURCE_BYTES:
        raise base.ProcessingFailure(
            "MEDIA_RESOURCE_LIMIT",
            "The recording exceeds the bounded source-size limit. The original remains unchanged for manual review.",
        )
    if not _header_matches(data, extension):
        raise base.ProcessingFailure(
            "MEDIA_HEADER_INVALID",
            "The material does not contain the expected recording header. The original remains unchanged for review.",
        )
    payload = _run_worker(data, extension, timeout_seconds=worker_timeout_seconds)
    text, facts = payload.get("text"), payload.get("facts")
    if not isinstance(text, str) or not text or len(text) > base.MAX_DERIVED_CHARACTERS or not isinstance(facts, dict):
        raise base.ProcessingFailure(
            "MEDIA_WORKER_FAILED",
            "The isolated transcription worker returned an invalid result. The original remains unchanged.",
        )
    if facts.get("processor") != PROCESSOR or facts.get("processor_version") != PROCESSOR_VERSION:
        raise base.ProcessingFailure(
            "MEDIA_WORKER_FAILED",
            "The isolated transcription worker identity could not be verified. The original remains unchanged.",
        )
    hashes = (
        str(facts.get("normalized_sha256", "")), str(facts.get("model_sha256", "")),
        str(facts.get("whisper_binary_sha256", "")),
    )
    if not all(_full_sha256(value) for value in hashes):
        raise base.ProcessingFailure(
            "MEDIA_WORKER_FAILED",
            "The transcription processing lineage could not be verified. The original remains unchanged.",
        )
    duration = float(facts.get("duration_seconds", -1))
    if duration <= 0 or duration > 3600:
        raise base.ProcessingFailure(
            "MEDIA_WORKER_FAILED",
            "The transcription worker returned an invalid duration. The original remains unchanged.",
        )
    method = (
        f"Isolated bounded English spoken-word transcription by {PROCESSOR} {PROCESSOR_VERSION}; "
        f"container={str(facts.get('container', 'unknown'))[:40]}; codec={str(facts.get('codec', 'unknown'))[:40]}; "
        f"audio-stream={int(facts.get('audio_stream_index', -1))}; duration-seconds={duration:.3f}; "
        f"normalized=mono/16000Hz/s16le; normalized-sha256={hashes[0]}; "
        f"ffmpeg={str(facts.get('ffmpeg_version', 'unknown'))[:100]}; "
        f"whisper.cpp={str(facts.get('whisper_release', 'unknown'))[:40]}; "
        f"whisper-binary-sha256={hashes[2]}; model=tiny.en; model-sha256={hashes[1]}; "
        "fixed English transcription; approximate timestamps; no video-frame analysis, speaker identity, "
        "biometrics, emotion or credibility inference, translation, external retrieval, or human review"
    )
    return text, method, bool(payload.get("truncated")), PROCESSOR, PROCESSOR_VERSION


def _full_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


_ORIGINAL_DECODER = image._decode_image


def register_salcapa_audio_video_processing(fastapi_app, core: dict) -> None:
    """Install the media worker chain and register governed orchestration once."""
    base._decode_inert_text = _decode_media
    base.register_salcapa_material_processing(fastapi_app, core)
