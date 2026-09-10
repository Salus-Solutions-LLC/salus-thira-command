#!/usr/bin/env python3
"""Isolated adapter for one hash-approved local handwriting/OCR processor."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import resource
import subprocess
import sys


MAX_ADDRESS_SPACE = 768 * 1024 * 1024
MAX_CPU_SECONDS = 45
MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_OPEN_FILES = 48
MAX_OUTPUT_BYTES = 2 * 1024 * 1024
MAX_SEGMENTS = 500


class WorkerFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail); self.code, self.detail = code, detail


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True)); return True
    except (OSError, ValueError):
        return False


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE, MAX_ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))
    os.umask(0o077)


def _load(path: Path) -> dict:
    try: payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerFailure("OCR_REQUEST_INVALID", "The bounded recognition request could not be read safely.") from exc
    if not isinstance(payload, dict): raise WorkerFailure("OCR_REQUEST_INVALID", "The bounded recognition request is invalid.")
    return payload


def run(request_path: Path) -> dict:
    request = _load(request_path); root = Path(str(request.get("profile_root", "")))
    source = Path(str(request.get("source_path", ""))); executable = Path(str(request.get("executable_path", "")))
    model = Path(str(request.get("model_path", ""))); language_data = Path(str(request.get("language_data_path", "")))
    if not root.is_absolute() or not all(_contained(path, root) for path in (executable, model, language_data)):
        raise WorkerFailure("OCR_PROFILE_INVALID", "The approved recognition profile boundary is invalid.")
    if not source.is_file() or _sha(source) != request.get("source_sha256"):
        raise WorkerFailure("OCR_SOURCE_MISMATCH", "The governed source image could not be verified.")
    expected = (request.get("executable_sha256"), request.get("model_sha256"), request.get("language_data_sha256"))
    if any(_sha(path) != digest for path, digest in zip((executable, model, language_data), expected)):
        raise WorkerFailure("OCR_ARTIFACT_MISMATCH", "An approved recognition artifact could not be verified.")
    mode = request.get("mode")
    if mode not in request.get("modes", []): raise WorkerFailure("OCR_MODE_UNSUPPORTED", "The recognition mode is outside the approved profile.")
    try:
        completed = subprocess.run(
            [str(executable), "--source", str(source), "--model", str(model), "--language-data", str(language_data), "--mode", str(mode), "--request", str(request_path)],
            cwd=str(root), env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(request.get("timeout_seconds", 30)), check=False, start_new_session=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerFailure("OCR_PROCESSOR_UNAVAILABLE", "The approved local recognition process did not complete within its bounded operating limit.") from exc
    if completed.returncode != 0 or len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise WorkerFailure("OCR_PROCESSOR_FAILED", "The approved local recognition process returned no usable bounded result.")
    try: output = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerFailure("OCR_OUTPUT_INVALID", "The approved local recognition process returned an invalid result.") from exc
    segments = output.get("segments") if isinstance(output, dict) else None
    maximum = min(MAX_SEGMENTS, int(request.get("max_segments", 100)))
    if output.get("ok") is not True or not isinstance(segments, list) or len(segments) > maximum:
        raise WorkerFailure("OCR_OUTPUT_INVALID", "The approved local recognition process returned an invalid segment set.")
    region = request.get("region", {}); allowed_types = {"printed", "handwritten", "mixed", "mark", "checkbox", "field", "table", "unknown", "illegible"}
    languages, scripts = set(request.get("languages", [])), set(request.get("scripts", [])); results = []; characters = 0; orders = set()
    for item in segments:
        if not isinstance(item, dict): raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned an invalid segment.")
        text = item.get("text"); segment_type = item.get("segment_type"); box = item.get("region")
        if not isinstance(text, str) or len(text) > 12000 or any(ord(char) < 32 and char not in "\n\t" for char in text):
            raise WorkerFailure("OCR_OUTPUT_TEXT", "The recognition process returned invalid prepared text.")
        if segment_type not in allowed_types or not isinstance(box, dict):
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned an invalid segment type or region.")
        try:
            order = int(item["reading_order"]); x, y, width, height = (int(box[name]) for name in ("x", "y", "width", "height")); score = float(item["score"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned invalid bounded values.") from exc
        if order < 1 or order in orders or min(x, y) < 0 or min(width, height) < 1 or x + width > region.get("width", 0) or y + height > region.get("height", 0) or not math.isfinite(score) or not 0 <= score <= 1:
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned values outside approved bounds.")
        language, script = item.get("language"), item.get("script")
        if language not in languages or script not in scripts:
            raise WorkerFailure("OCR_OUTPUT_LANGUAGE", "The recognition process returned a language or script outside the approved profile.")
        alternatives, uncertain = item.get("alternatives", []), item.get("uncertain_spans", [])
        if not isinstance(alternatives, list) or len(alternatives) > 10 or any(not isinstance(value, str) or len(value) > 12000 for value in alternatives):
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned invalid alternate readings.")
        if not isinstance(uncertain, list) or len(uncertain) > 100:
            raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned invalid uncertainty spans.")
        for span in uncertain:
            if not isinstance(span, dict) or set(span) - {"start", "end", "alternatives", "reason"}: raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned an invalid uncertainty span.")
            try: start, end = int(span["start"]), int(span["end"])
            except (KeyError, TypeError, ValueError) as exc: raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned an invalid uncertainty range.") from exc
            if start < 0 or end <= start or end > len(text) or not isinstance(span.get("alternatives", []), list) or len(span.get("alternatives", [])) > 10:
                raise WorkerFailure("OCR_OUTPUT_INVALID", "The recognition process returned an uncertainty range outside the prepared text.")
        orders.add(order); characters += len(text)
        if characters > int(request.get("max_characters", 50000)): raise WorkerFailure("OCR_OUTPUT_LIMIT", "The prepared text exceeded the approved character limit.")
        results.append({"reading_order": order, "text": text, "segment_type": segment_type, "score": format(score, ".6f"), "alternatives": alternatives, "uncertain_spans": uncertain, "limitations": str(item.get("limitations", ""))[:2000], "region_x": region["x"] + x, "region_y": region["y"] + y, "region_width": width, "region_height": height, "language": language, "script": script})
    results.sort(key=lambda value: value["reading_order"])
    return {"ok": True, "segments": results}


def main() -> None:
    _limits()
    try:
        if len(sys.argv) != 2: raise WorkerFailure("OCR_REQUEST_INVALID", "The bounded recognition worker received invalid input.")
        result = run(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":"))); raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "OCR_WORKER_FAILED", "detail": "The local text-recognition review could not be completed safely."}, separators=(",", ":"))); raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__": main()
