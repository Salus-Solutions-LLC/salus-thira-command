#!/usr/bin/env python3
"""Isolated adapter for one hash-approved, deployment-supplied visual processor."""

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
MAX_OUTPUT_BYTES = 1024 * 1024
MAX_SUGGESTIONS = 100
PROCESSOR = "SalCAPA Governed Local Visual Processor Adapter"
PROCESSOR_VERSION = "1.0.0"


class WorkerFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code, self.detail = code, detail


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _contained(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=True).relative_to(root.resolve(strict=True))
        return True
    except (OSError, ValueError):
        return False


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_CPU_SECONDS, MAX_CPU_SECONDS + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE, MAX_ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))
    os.umask(0o077)


def _load(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerFailure("VISUAL_REQUEST_INVALID", "The bounded visual request could not be read safely.") from exc
    if not isinstance(payload, dict):
        raise WorkerFailure("VISUAL_REQUEST_INVALID", "The bounded visual request is invalid.")
    return payload


def run(request_path: Path) -> dict:
    request = _load(request_path)
    root = Path(str(request.get("profile_root", "")))
    source = Path(str(request.get("source_path", "")))
    executable = Path(str(request.get("executable_path", "")))
    model = Path(str(request.get("model_path", "")))
    if not root.is_absolute() or not all(_contained(path, root) for path in (executable, model)):
        raise WorkerFailure("VISUAL_PROFILE_INVALID", "The approved visual processor boundary is invalid.")
    if not source.is_file() or _sha(source) != request.get("source_sha256"):
        raise WorkerFailure("VISUAL_SOURCE_MISMATCH", "The governed image source could not be verified.")
    if _sha(executable) != request.get("executable_sha256") or _sha(model) != request.get("model_sha256"):
        raise WorkerFailure("VISUAL_ARTIFACT_MISMATCH", "An approved visual processor artifact could not be verified.")
    vocabulary = request.get("vocabulary")
    allowed = {item.get("id"): item for item in vocabulary or [] if isinstance(item, dict)}
    if not allowed or any(not isinstance(key, str) or not key for key in allowed):
        raise WorkerFailure("VISUAL_VOCABULARY_INVALID", "The approved category vocabulary is invalid.")
    try:
        completed = subprocess.run(
            [str(executable), "--source", str(source), "--model", str(model), "--request", str(request_path)],
            cwd=str(root), env={"LC_ALL": "C.UTF-8", "PYTHONHASHSEED": "0", "PATH": "/usr/bin:/bin"},
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=int(request.get("timeout_seconds", 30)), check=False, start_new_session=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkerFailure("VISUAL_PROCESSOR_UNAVAILABLE", "The approved local visual processor did not complete within its bounded operating limit.") from exc
    if completed.returncode != 0 or len(completed.stdout) > MAX_OUTPUT_BYTES:
        raise WorkerFailure("VISUAL_PROCESSOR_FAILED", "The approved local visual processor returned no usable bounded result.")
    try:
        output = json.loads(completed.stdout.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise WorkerFailure("VISUAL_OUTPUT_INVALID", "The approved local visual processor returned an invalid result.") from exc
    detections = output.get("detections") if isinstance(output, dict) else None
    if output.get("ok") is not True or not isinstance(detections, list) or len(detections) > MAX_SUGGESTIONS:
        raise WorkerFailure("VISUAL_OUTPUT_INVALID", "The approved local visual processor returned an invalid result.")
    region = request["region"]
    results = []
    for item in detections:
        if not isinstance(item, dict) or item.get("category_id") not in allowed:
            raise WorkerFailure("VISUAL_OUTPUT_CATEGORY", "The processor returned a category outside its approved vocabulary.")
        box = item.get("region")
        if not isinstance(box, dict):
            raise WorkerFailure("VISUAL_OUTPUT_REGION", "The processor returned an invalid source region.")
        try:
            x, y, width, height = (int(box[name]) for name in ("x", "y", "width", "height"))
            score = float(item["score"])
        except (KeyError, TypeError, ValueError, OverflowError) as exc:
            raise WorkerFailure("VISUAL_OUTPUT_INVALID", "The processor returned invalid bounded values.") from exc
        if min(x, y) < 0 or min(width, height) < 1 or x + width > region["width"] or y + height > region["height"] or not math.isfinite(score) or not 0 <= score <= 1:
            raise WorkerFailure("VISUAL_OUTPUT_INVALID", "The processor returned values outside the approved bounds.")
        alternatives = item.get("alternatives", [])
        if not isinstance(alternatives, list) or len(alternatives) > 5 or any(value not in allowed for value in alternatives):
            raise WorkerFailure("VISUAL_OUTPUT_INVALID", "The processor returned invalid category alternatives.")
        results.append({
            "category_id": item["category_id"], "display_label": allowed[item["category_id"]]["label"],
            "score": format(score, ".6f"), "region_x": region["x"] + x, "region_y": region["y"] + y,
            "region_width": width, "region_height": height, "alternatives": alternatives,
            "limitations": str(item.get("limitations", ""))[:1000],
        })
    return {"ok": True, "processor": PROCESSOR, "processor_version": PROCESSOR_VERSION, "suggestions": results}


def main() -> None:
    _limits()
    try:
        if len(sys.argv) != 2:
            raise WorkerFailure("VISUAL_REQUEST_INVALID", "The bounded visual worker received invalid input.")
        result = run(Path(sys.argv[1]))
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":")))
        raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "VISUAL_WORKER_FAILED", "detail": "The local visual review could not be completed safely."}, separators=(",", ":")))
        raise SystemExit(2)
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
