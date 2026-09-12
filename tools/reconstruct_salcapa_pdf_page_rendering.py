#!/usr/bin/env python3
"""Reconstruct reviewed selected-page PDF rendering sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_pdf_page_rendering.py.gz", "salcapa_pdf_page_rendering.py", "1256fddcdaf161f06da341835539672947091e3936e39b691a33a9d3ad4f5133", "fd2bc654c0b9aeb491ff02b43c591ce660a325b2183507579b51813879e0464d", 31609),
    ("salcapa_pdf_render_worker.py.gz", "tools/salcapa_pdf_render_worker.py", "9fe5dc26b9480feeca3bcfbb6629bad7370a29d4a2c137d2a47415b459c5d864", "b52895ec7a8c1a5a8abe671139e15c80112a89cb15c5410891834743b8196042", 9041),
    ("ci_salcapa_pdf_page_rendering_smoke.py.gz", "tools/ci_salcapa_pdf_page_rendering_smoke.py", "d9ec378c8574aacfb01fadc53254e0484cc997ff05260c5bdeda0da4345c21be", "2c5f61330a4d199a38d4cd814e11ee35c3aecc9e9beb665c1dacf0acc7c0f8ce", 11680),
)

for archive_name, target_name, archive_sha, target_sha, target_size in ARTIFACTS:
    compressed = (ROOT / "source_archives/development" / archive_name).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive_name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target_name}")
    target = ROOT / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

print("SALCAPA_PDF_PAGE_RENDERING_RECONSTRUCTION_PASS")
