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
    (
        ROOT / "source_archives/development/salcapa_pdf_worker.py.gz",
        ROOT / "tools/salcapa_pdf_worker.py",
        "e1a72fdd248f32d4c7f18ac733d187af0eae77300c5d0243d41de74927e47f63",
        "7215431ab29e3290a353be0194788bfd05ec12383412719f67018bc872d5360b",
        10584,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_pdf_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_pdf_processing_smoke.py",
        "406080aa817c6acbc76a24683d66bb581334e4072f2dc68804a59c3698a64858",
        "277ca74129d168cc9fa2f591e3f94dd9b3d2e45a2844fcf5c0d02c5c26eb7d09",
        11030,
    ),
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
print("SALCAPA_PDF_PROCESSING_RECONSTRUCTION_PASS")
