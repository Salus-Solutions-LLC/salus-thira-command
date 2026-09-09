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
        "40b117194088173bce545b6613def2127cda038c3174f015eaad81e3f8b012ae",
        "f7597d5a1bbe5dcbad5aae0b311bdb6bac42bf54f9d43a19d1972d6d6fd6e3c2",
        10410,
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
