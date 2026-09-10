#!/usr/bin/env python3
"""Isolated, bounded English spoken-word transcription for approved recordings."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile


MAX_ADDRESS_SPACE = 768 * 1024 * 1024
MAX_CPU_SECONDS = 20 * 60
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_OPEN_FILES = 64
MAX_DURATION_SECONDS = 3600.0
MAX_PROBE_BYTES = 256 * 1024
MAX_TRANSCRIPT_BYTES = 8 * 1024 * 1024
MAX_CHARACTERS = 500_000
MAX_SEGMENTS = 20_000
PROBE_TIMEOUT_SECONDS = 10
DECODE_TIMEOUT_SECONDS = 120
TRANSCRIPTION_TIMEOUT_SECONDS = 20 * 60
PROCESSOR = "SalCAPA Isolated Audio and Video Transcript Preparer"
PROCESSOR_VERSION = "1.0.0"
FFPROBE = Path("/usr/bin/ffprobe")
FFMPEG = Path("/usr/bin/ffmpeg")
ASSET_ROOT = Path("/opt/whisper")
WHISPER = ASSET_ROOT / "bin" / "whisper-cli"
MODEL = ASSET_ROOT / "models" / "ggml-tiny.en.bin"
MANIFEST = ASSET_ROOT / "manifest.json"
WHISPER_RELEASE = "b4938"
WHISPER_ARCHIVE_SHA256 = "f4cfc1f969a13805908fb72043ce7cc896eb42e0b8afbe841dc8e7298923b061"
MODEL_SHA256 = "921e4cf8686fdd993dcd081a5da5b6c365bfde1162e72b08d75ac75289920b1f"
DEMUXERS = {"wav": "wav", "mp3": "mp3", "mp4": "mov"}
CONTAINERS = {"wav": {"wav"}, "mp3": {"mp3"}, "mp4": {"mov,mp4,m4a,3gp,3g2,mj2"}}
CODECS = {"wav": {"pcm_s16le"}, "mp3": {"mp3"}, "mp4": {"aac"}}


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


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _version(binary: Path, label: str) -> str:
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise WorkerFailure("TRANSCRIPTION_UNAVAILABLE", f"The approved {label} component is unavailable. Manual review remains available.")
    try:
        result = subprocess.run(
            [str(binary), "-version" if label == "FFmpeg" else "--version"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=5, check=False, env={"LC_ALL": "C.UTF-8", "LD_LIBRARY_PATH": str(ASSET_ROOT / "lib")},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerFailure("TRANSCRIPTION_UNAVAILABLE", f"The approved {label} component is unavailable. Manual review remains available.") from exc
    first = result.stdout.decode("utf-8", errors="replace").splitlines()[0] if result.stdout else ""
    if result.returncode != 0 or not first or len(first) > 500:
        raise WorkerFailure("TRANSCRIPTION_UNAVAILABLE", f"The approved {label} component identity could not be verified.")
    return first[:100]


def _verify_assets() -> dict:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerFailure("TRANSCRIPTION_UNAVAILABLE", "The approved transcription manifest is unavailable. Manual review remains available.") from exc
    required = {
        "release": WHISPER_RELEASE,
        "archive_sha256": WHISPER_ARCHIVE_SHA256,
        "model": "tiny.en",
        "model_sha256": MODEL_SHA256,
    }
    if any(manifest.get(key) != value for key, value in required.items()):
        raise WorkerFailure("TRANSCRIPTION_MODEL_INVALID", "The approved transcription manifest does not match the release contract.")
    binary_hash = _sha(WHISPER) if WHISPER.is_file() else ""
    model_hash = _sha(MODEL) if MODEL.is_file() else ""
    if binary_hash != manifest.get("binary_sha256") or model_hash != MODEL_SHA256:
        raise WorkerFailure("TRANSCRIPTION_MODEL_INVALID", "The transcription binary or English model integrity check failed.")
    return {"whisper_binary_sha256": binary_hash, "model_sha256": model_hash}


def _run(command: list[str], timeout: int, code: str, detail: str, *, cwd: Path) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            command, cwd=cwd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=timeout, check=False,
            env={"HOME": str(cwd), "TMPDIR": str(cwd), "LC_ALL": "C.UTF-8", "LD_LIBRARY_PATH": str(ASSET_ROOT / "lib")},
        )
    except subprocess.TimeoutExpired as exc:
        raise WorkerFailure("MEDIA_RESOURCE_LIMIT", "The recording exceeded a bounded processing time. The original remains unchanged.") from exc
    except OSError as exc:
        raise WorkerFailure("TRANSCRIPTION_UNAVAILABLE", "A required local transcription component could not start. Manual review remains available.") from exc
    if result.returncode != 0:
        raise WorkerFailure(code, detail)
    return result


def _probe(path: Path, extension: str) -> tuple[dict, dict]:
    result = _run([
        str(FFPROBE), "-v", "error", "-protocol_whitelist", "file,pipe", "-f", DEMUXERS[extension],
        "-show_format", "-show_streams", "-of", "json", str(path),
    ], PROBE_TIMEOUT_SECONDS, "MEDIA_PROBE_FAILED", "The recording could not be inspected safely. The original remains unchanged.", cwd=path.parent)
    if len(result.stdout) > MAX_PROBE_BYTES:
        raise WorkerFailure("MEDIA_RESOURCE_LIMIT", "The recording inspection exceeded the bounded output limit.")
    try:
        payload = json.loads(result.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise WorkerFailure("MEDIA_PROBE_FAILED", "The recording inspection returned an invalid result.") from exc
    streams = payload.get("streams")
    format_data = payload.get("format")
    if not isinstance(streams, list) or not isinstance(format_data, dict) or not 1 <= len(streams) <= 2:
        raise WorkerFailure("MEDIA_STREAM_LIMIT", "The recording has an unsupported number of streams. The original remains unchanged.")
    audio = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "audio"]
    video = [item for item in streams if isinstance(item, dict) and item.get("codec_type") == "video"]
    forbidden = [item for item in streams if isinstance(item, dict) and item.get("codec_type") not in {"audio", "video"}]
    if len(audio) != 1 or forbidden or (extension != "mp4" and video) or len(video) > 1:
        raise WorkerFailure("MEDIA_STREAM_INVALID", "The recording contains unsupported, missing, or alternate streams. The original remains unchanged.")
    stream = audio[0]
    if stream.get("codec_name") not in CODECS[extension]:
        raise WorkerFailure("MEDIA_FORMAT_MISMATCH", "The recording codec does not match the approved format. The original remains unchanged.")
    format_name = str(format_data.get("format_name", ""))
    if format_name not in CONTAINERS[extension]:
        raise WorkerFailure("MEDIA_FORMAT_MISMATCH", "The detected recording container does not match the approved format.")
    try:
        duration = float(stream.get("duration") or format_data.get("duration"))
        sample_rate = int(stream.get("sample_rate"))
        channels = int(stream.get("channels"))
        index = int(stream.get("index"))
    except (TypeError, ValueError) as exc:
        raise WorkerFailure("MEDIA_OUTPUT_INVALID", "The recording contains invalid stream facts.") from exc
    if not 0 < duration <= MAX_DURATION_SECONDS:
        raise WorkerFailure("MEDIA_DURATION_LIMIT", "The recording duration exceeds the bounded transcription limit.")
    if not 1 <= channels <= 2 or not 8_000 <= sample_rate <= 96_000 or index < 0:
        raise WorkerFailure("MEDIA_STREAM_INVALID", "The recording audio configuration is outside the approved limits.")
    return stream, {
        "container": format_name, "codec": stream["codec_name"], "duration_seconds": duration,
        "source_sample_rate": sample_rate, "source_channels": channels, "audio_stream_index": index,
        "stream_count": len(streams), "video_stream_present": bool(video),
    }


def _decode(path: Path, extension: str, stream_index: int, normalized: Path) -> None:
    _run([
        str(FFMPEG), "-v", "error", "-nostdin", "-protocol_whitelist", "file,pipe",
        "-f", DEMUXERS[extension], "-i", str(path), "-map", f"0:{stream_index}",
        "-vn", "-sn", "-dn", "-map_metadata", "-1", "-map_chapters", "-1",
        "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", "-f", "wav", str(normalized),
    ], DECODE_TIMEOUT_SECONDS, "MEDIA_DECODE_FAILED", "The approved audio stream could not be decoded safely. The original remains unchanged.", cwd=path.parent)
    try:
        size = normalized.stat().st_size
        with normalized.open("rb") as handle:
            header = handle.read(12)
    except OSError as exc:
        raise WorkerFailure("MEDIA_OUTPUT_INVALID", "The normalized audio output is unavailable.") from exc
    if not 44 <= size <= 120 * 1024 * 1024 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise WorkerFailure("MEDIA_OUTPUT_INVALID", "The normalized audio output is invalid or exceeds the bounded limit.")


_SRT_TIME = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})$")


def _seconds(value: str) -> float:
    match = _SRT_TIME.fullmatch(value)
    if not match:
        raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript contains an invalid approximate timestamp.")
    hours, minutes, seconds, milliseconds = (int(item) for item in match.groups())
    if minutes > 59 or seconds > 59:
        raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript contains an invalid approximate timestamp.")
    return hours * 3600 + minutes * 60 + seconds + milliseconds / 1000


def _parse_srt(path: Path, duration: float) -> tuple[str, int, bool]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript output is unavailable.") from exc
    if len(raw) > MAX_TRANSCRIPT_BYTES:
        raise WorkerFailure("MEDIA_RESOURCE_LIMIT", "The transcript exceeded the bounded output limit.")
    try:
        text = raw.decode("utf-8", errors="strict").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError as exc:
        raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript output is not valid UTF-8.") from exc
    blocks = [block for block in text.split("\n\n") if block.strip()]
    if len(blocks) > MAX_SEGMENTS:
        raise WorkerFailure("MEDIA_RESOURCE_LIMIT", "The transcript exceeded the bounded segment limit.")
    lines: list[str] = []
    previous = 0.0
    for position, block in enumerate(blocks, start=1):
        parts = block.splitlines()
        if len(parts) < 3 or parts[0].strip() != str(position) or " --> " not in parts[1]:
            raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript output structure is invalid.")
        start_raw, end_raw = parts[1].split(" --> ", 1)
        start, end = _seconds(start_raw.strip()), _seconds(end_raw.strip())
        if start < previous or end < start or end > duration + 2.0:
            raise WorkerFailure("TRANSCRIPT_OUTPUT_INVALID", "The transcript timestamps are outside the source duration.")
        proposed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", " ".join(parts[2:])).strip()
        if proposed:
            lines.append(f"[{start:.3f}–{end:.3f} seconds] {proposed}")
        previous = end
    joined = "\n".join(lines)
    truncated = len(joined) > MAX_CHARACTERS
    return joined[:MAX_CHARACTERS], len(lines), truncated


def _transcribe(normalized: Path, duration: float) -> tuple[str, dict, bool]:
    lineage = _verify_assets()
    # The exact executable hash in the signed build manifest is the identity
    # control. The release binary does not expose a stable version CLI flag.
    whisper_version = f"whisper.cpp {WHISPER_RELEASE}"
    prefix = normalized.parent / "transcript"
    result = _run([
        str(WHISPER), "-m", str(MODEL), "-f", str(normalized), "-l", "en",
        "-t", "1", "-bs", "1", "-bo", "1", "-np", "-nt", "-osrt", "-of", str(prefix), "--no-gpu",
    ], TRANSCRIPTION_TIMEOUT_SECONDS, "TRANSCRIPTION_FAILED", "English spoken words could not be prepared safely. The original remains unchanged.", cwd=normalized.parent)
    if len(result.stdout) + len(result.stderr) > MAX_TRANSCRIPT_BYTES:
        raise WorkerFailure("MEDIA_RESOURCE_LIMIT", "The transcription process exceeded the bounded output limit.")
    text, segment_count, truncated = _parse_srt(prefix.with_suffix(".srt"), duration)
    return text, {
        **lineage, "whisper_release": WHISPER_RELEASE, "whisper_version": whisper_version,
        "model": "tiny.en", "language": "en", "segment_count": segment_count,
        "timestamps": "approximate", "normalized_audio_retained": False,
    }, truncated


def extract(path: Path) -> dict:
    extension = path.suffix.lower().removeprefix(".")
    if extension not in DEMUXERS:
        raise WorkerFailure("MEDIA_FORMAT_MISMATCH", "The recording format is not supported by this bounded worker.")
    ffprobe_version = _version(FFPROBE, "FFmpeg")
    ffmpeg_version = _version(FFMPEG, "FFmpeg")
    with tempfile.TemporaryDirectory(prefix="salcapa-transcript-", dir=path.parent) as directory:
        normalized = Path(directory) / "normalized.wav"
        stream, media_facts = _probe(path, extension)
        _decode(path, extension, int(stream["index"]), normalized)
        normalized_hash = _sha(normalized)
        transcript, recognition_facts, truncated = _transcribe(normalized, float(media_facts["duration_seconds"]))
    sections = [
        "[English spoken-word transcript — Derived — Unverified]",
        transcript or "[Spoken words not reliably recognized — human review needed]",
        "", "[Processing limitations]",
        "Words, punctuation, speaker boundaries, and timestamps are proposed and require comparison with the original recording. No speaker identification, biometric analysis, emotion or credibility inference, translation, video-frame analysis, external retrieval, or human review occurred.",
    ]
    return {"ok": True, "text": "\n".join(sections), "truncated": truncated, "facts": {
        "processor": PROCESSOR, "processor_version": PROCESSOR_VERSION,
        "ffprobe_version": ffprobe_version, "ffmpeg_version": ffmpeg_version,
        "normalized_sha256": normalized_hash, **media_facts, **recognition_facts,
    }}


def main() -> None:
    _apply_limits()
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "MEDIA_WORKER_INPUT_INVALID", "detail": "The transcription worker received invalid input."}))
        raise SystemExit(2)
    try:
        result = extract(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":")))
        raise SystemExit(2)
    except (MemoryError, RecursionError):
        print(json.dumps({"ok": False, "code": "MEDIA_RESOURCE_LIMIT", "detail": "The recording exceeded bounded processing resources."}, separators=(",", ":")))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "MEDIA_WORKER_FAILED", "detail": "The isolated transcription worker could not complete safely. The original remains unchanged."}, separators=(",", ":")))
        raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
