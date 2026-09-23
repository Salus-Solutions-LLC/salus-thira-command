#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 PDF-processing sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_pdf_processing.py.gz",
        ROOT / "salcapa_pdf_processing.py",
        "ee24fc47d26bd404030c16d6597e7e6dd6047367b5457c743dd92517131db388",
        "f22e668dac095ab03b3d75863aabd52aaa2a1dd5aa0b9e80eea273313375e255",
        7864,
    ),
)

# These files now have reviewed source changes beyond their historical archives.
# Verify the checked-in versions before the container can compile or ship them.
CURRENT_SOURCES = (
    (ROOT / "tools/salcapa_pdf_worker.py",
     "5c3d29a5fb5396af3659f2eaadf0cdaf65922b0a291c04e0d127878ae184088b", 11325),
    (ROOT / "tools/ci_salcapa_pdf_processing_smoke.py",
     "42e2a7f85392c99550e6d81c815ba0f1a71c1e36d1aa1177ee8ddca4f64613ae", 12186),
)

for archive, target, archive_sha, target_sha, target_size in ARTIFACTS:
    compressed = archive.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive.name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
for target, expected_sha, expected_size in CURRENT_SOURCES:
    content = target.read_bytes()
    if len(content) != expected_size or hashlib.sha256(content).hexdigest() != expected_sha:
        raise SystemExit(f"Invalid current PDF source: {target.name}")
print("SALCAPA_PDF_PROCESSING_RECONSTRUCTION_PASS")
