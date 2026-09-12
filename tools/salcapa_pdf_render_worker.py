#!/usr/bin/env python3
"""Isolated worker for hash-bound rendering of selected PDF pages."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time


MAX_ADDRESS_SPACE = 512 * 1024 * 1024
MAX_FILE_BYTES = 512 * 1024 * 1024
MAX_OPEN_FILES = 64


class WorkerFailure(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail); self.code = code; self.detail = detail


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()


def apply_limits(timeout_seconds: int) -> None:
    cpu = max(5, min(90, timeout_seconds))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu + 1))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_ADDRESS_SPACE, MAX_ADDRESS_SPACE))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE_BYTES, MAX_FILE_BYTES))
    resource.setrlimit(resource.RLIMIT_NOFILE, (MAX_OPEN_FILES, MAX_OPEN_FILES))
    os.umask(0o077)


def finite_box(box) -> list[float]:
    import math
    values = [float(item) for item in box]
    if len(values) != 4 or not all(math.isfinite(item) for item in values): raise ValueError
    if values[2] <= values[0] or values[3] <= values[1]: raise ValueError
    return values


def render(manifest: dict) -> dict:
    required = {"source_path", "source_sha256", "output_dir", "pages", "executable_path", "executable_sha256",
                "dpi", "max_pages", "max_pixels_per_page", "max_total_pixels", "max_output_bytes_per_page",
                "max_total_output_bytes", "timeout_seconds", "external_processing", "no_network"}
    if not isinstance(manifest, dict) or not required.issubset(manifest):
        raise WorkerFailure("PDF_RENDER_INPUT_INVALID", "The isolated page renderer received an invalid request.")
    source, output_dir, executable = Path(manifest["source_path"]), Path(manifest["output_dir"]), Path(manifest["executable_path"])
    if not source.is_file() or not output_dir.is_dir() or not executable.is_file():
        raise WorkerFailure("PDF_RENDER_INPUT_INVALID", "The isolated page renderer could not verify its bounded inputs.")
    if sha(source) != manifest["source_sha256"] or sha(executable) != manifest["executable_sha256"]:
        raise WorkerFailure("PDF_RENDER_INTEGRITY", "The source or renderer hash did not match the approved request.")
    if manifest["external_processing"] is not False or manifest["no_network"] is not True:
        raise WorkerFailure("PDF_RENDER_POLICY", "The request did not enforce local no-network rendering.")
    pages = manifest["pages"]
    if not isinstance(pages, list) or not 1 <= len(pages) <= min(12, int(manifest["max_pages"])):
        raise WorkerFailure("PDF_RENDER_PAGE_LIMIT", "The selected page set is outside the governed boundary.")
    numbers = [int(item.get("page_number", 0)) for item in pages if isinstance(item, dict)]
    if len(numbers) != len(pages) or any(number < 1 for number in numbers) or len(numbers) != len(set(numbers)):
        raise WorkerFailure("PDF_RENDER_INPUT_INVALID", "The selected page set is invalid.")
    timeout = int(manifest["timeout_seconds"]); apply_limits(timeout)
    from pypdf import PdfReader
    from PIL import Image
    try: reader = PdfReader(source, strict=True, root_object_recovery_limit=10_000)
    except Exception as exc: raise WorkerFailure("PDF_RENDER_PARSE_FAILED", "The PDF could not be reopened in strict mode for rendering.") from exc
    if reader.is_encrypted: raise WorkerFailure("PDF_RENDER_POLICY", "Encrypted PDFs are not rendered.")
    labels = []
    try: labels = list(reader.page_labels)
    except Exception: pass
    started = time.monotonic(); results = []; total_pixels = total_bytes = 0
    try:
        for number in numbers:
            if number > len(reader.pages): raise WorkerFailure("PDF_RENDER_PAGE_LIMIT", "A selected page is outside the PDF page set.")
            page = reader.pages[number - 1]
            try:
                media_box = finite_box([page.mediabox.left, page.mediabox.bottom, page.mediabox.right, page.mediabox.top])
                crop_box = finite_box([page.cropbox.left, page.cropbox.bottom, page.cropbox.right, page.cropbox.top])
                rotation = int(page.rotation or 0) % 360
                user_unit = float(page.get("/UserUnit", 1) or 1)
                if rotation not in {0, 90, 180, 270} or not 0 < user_unit <= 75_000: raise ValueError
            except Exception as exc: raise WorkerFailure("PDF_RENDER_GEOMETRY", "A selected page contains unsupported geometry.") from exc
            prefix = output_dir / f"page-{number:04d}"; output = output_dir / f"page-{number:04d}.png"
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0: raise WorkerFailure("PDF_RENDER_RESOURCE_LIMIT", "The page-rendering request exceeded its time limit.")
            try:
                completed = subprocess.run([str(executable), "-f", str(number), "-l", str(number), "-r", str(int(manifest["dpi"])),
                    "-png", "-singlefile", "-cropbox", str(source), str(prefix)], cwd=output_dir,
                    env={"LC_ALL": "C.UTF-8", "HOME": str(output_dir), "PATH": "/usr/bin:/bin"},
                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=remaining, check=False, start_new_session=True)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise WorkerFailure("PDF_RENDER_RESOURCE_LIMIT", "The local page renderer did not complete within the bounded resources.") from exc
            if completed.returncode != 0 or len(completed.stdout) + len(completed.stderr) > 256_000 or not output.is_file():
                raise WorkerFailure("PDF_RENDER_FAILED", "The local page renderer did not produce a valid selected page.")
            try:
                with Image.open(output) as image:
                    width, height, image_format, mode = image.width, image.height, image.format, image.mode
                    image.verify()
            except Exception as exc: raise WorkerFailure("PDF_RENDER_OUTPUT_INVALID", "A rendered page failed image validation.") from exc
            if image_format != "PNG" or mode not in {"RGB", "RGBA"}: raise WorkerFailure("PDF_RENDER_OUTPUT_INVALID", "A rendered page used an unexpected format.")
            pixels, output_bytes = width * height, output.stat().st_size
            total_pixels += pixels; total_bytes += output_bytes
            if pixels > int(manifest["max_pixels_per_page"]) or output_bytes > int(manifest["max_output_bytes_per_page"]):
                raise WorkerFailure("PDF_RENDER_RESOURCE_LIMIT", "A rendered page exceeded the governed output boundary.")
            if total_pixels > int(manifest["max_total_pixels"]) or total_bytes > int(manifest["max_total_output_bytes"]):
                raise WorkerFailure("PDF_RENDER_RESOURCE_LIMIT", "The rendered page set exceeded the aggregate governed boundary.")
            results.append({"page_number": number, "source_page_label": str(labels[number - 1])[:200] if number <= len(labels) else "",
                "media_box": media_box, "crop_box": crop_box, "rotation": rotation, "user_unit": user_unit,
                "width": width, "height": height, "output_name": output.name, "rendered_sha256": sha(output),
                "limitations": "Rendered representation requires comparison with the original PDF; hidden conditions and source truth are not established."})
    finally:
        reader.close()
    expected = {item["output_name"] for item in results}
    if {path.name for path in output_dir.iterdir()} != expected:
        raise WorkerFailure("PDF_RENDER_OUTPUT_INVALID", "The renderer created unexpected output files.")
    return {"ok": True, "pages": results, "total_pixels": total_pixels, "total_output_bytes": total_bytes}


def main() -> None:
    if len(sys.argv) != 2:
        print(json.dumps({"ok": False, "code": "PDF_RENDER_INPUT_INVALID", "detail": "The page renderer received invalid input."})); raise SystemExit(2)
    try: manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")); result = render(manifest)
    except WorkerFailure as exc:
        print(json.dumps({"ok": False, "code": exc.code, "detail": exc.detail}, separators=(",", ":"))); raise SystemExit(2)
    except (MemoryError, RecursionError):
        print(json.dumps({"ok": False, "code": "PDF_RENDER_RESOURCE_LIMIT", "detail": "The page-rendering request exceeded bounded resources."}, separators=(",", ":"))); raise SystemExit(2)
    except Exception:
        print(json.dumps({"ok": False, "code": "PDF_RENDER_FAILED", "detail": "The isolated page renderer could not complete safely."}, separators=(",", ":"))); raise SystemExit(2)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
