#!/usr/bin/env python3
"""Reconstruct reviewed Issue #236 facility review-profile sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives" / "development" / "salcapa_facility_review_profiles.py.gz",
        ROOT / "salcapa_facility_review_profiles.py",
        "6a85a6c8cc33901df8cb93ea7ec0a64ab2727f62310974dcdef2d780e09d1e73",
        "349b6a698c399a4ca3a734e58b7ac872606563be60d12449407c043109f58999",
        20880,
    ),
    (
        ROOT / "source_archives" / "development" / "ci_salcapa_facility_review_profiles_smoke.py.gz",
        ROOT / "tools" / "ci_salcapa_facility_review_profiles_smoke.py",
        "0997a5210a1792972ff921e22356f37ca990997767d4e7154c4e218f661c1c64",
        "cc1d3f82221e1a79aefd0bb990f3b794f5703a96eb29b1f2ba05a2aa34633351",
        7677,
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

print("SALCAPA_FACILITY_REVIEW_PROFILES_RECONSTRUCTION_PASS")
