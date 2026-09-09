#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 Office-processing sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_office_processing.py.gz",
        ROOT / "salcapa_office_processing.py",
        "8fe52124ca408e155f6027a7087ee9f33807e79cfd541814acd2b36a898b3c54",
        "fc2a5f5a4cde371f9c4d8b7d8843751d9912c585a2d3de5e5308f8a3b88a56ef",
        12560,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_office_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_office_processing_smoke.py",
        "343fde99fbe1c454af5fee1240be87925234f3ce120690e77d3a9dbc31ac4775",
        "ca9c7324bf7a281ae88220ea3e30647d8f60adb4c488f7a56ba776324be9d32a",
        9366,
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
print("SALCAPA_OFFICE_PROCESSING_RECONSTRUCTION_PASS")
