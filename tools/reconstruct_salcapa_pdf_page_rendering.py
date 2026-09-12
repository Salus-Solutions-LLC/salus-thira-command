#!/usr/bin/env python3
"""Reconstruct reviewed selected-page PDF rendering sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_pdf_page_rendering.py.gz", "salcapa_pdf_page_rendering.py", "0661699abab699005c2fce11e64ff8ede195b1d13b1fd01e65caffc3a531727f", "f9711349f9810d273ad45fac5b1be208adce279ae357da1efd5b7bdabb6f71fa", 41808),
    ("salcapa_pdf_render_worker.py.gz", "tools/salcapa_pdf_render_worker.py", "9fe5dc26b9480feeca3bcfbb6629bad7370a29d4a2c137d2a47415b459c5d864", "b52895ec7a8c1a5a8abe671139e15c80112a89cb15c5410891834743b8196042", 9041),
    ("ci_salcapa_pdf_page_rendering_smoke.py.gz", "tools/ci_salcapa_pdf_page_rendering_smoke.py", "30a3605057f9027d3caa644e65f17ff34636c29b3ef7d840d91059cd7ab3f903", "5cf46093c04918051ac0b48c19d1d56e258d562958ce2b25bde91cd995903500", 16682),
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
