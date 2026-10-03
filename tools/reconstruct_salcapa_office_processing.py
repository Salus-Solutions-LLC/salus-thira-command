#!/usr/bin/env python3
"""Verify archived baselines and preserve reviewed Office-processing sources."""
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
    # The archive is a historical baseline. The reviewed tracked source has
    # since gained a damaged-central-directory guard and its regression test.
    # Never overwrite that source with the older archive during image builds.
    reviewed_sha = {
        "salcapa_office_processing.py": "c2a806df3158dcbc0dba10e4b5843d3c758f06bbb7224aa0734e366dfc841c69",
        "ci_salcapa_office_processing_smoke.py": "354a3493c8180ddb2fe32d2971af08ad37d66c7ef34e1d9074dc7bf2bdcb9f85",
    }[target.name]
    if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != reviewed_sha:
        raise SystemExit(f"Reviewed Office source missing or changed: {target.name}")
print("SALCAPA_OFFICE_PROCESSING_REVIEWED_SOURCE_PASS")
