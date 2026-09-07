#!/usr/bin/env python3
"""Reconstruct reviewed Issue #150 Facility Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "facility_assessment.py.gz",
     ROOT / "facility_assessment.py",
     "659206f1f028320ac9c81528a23f006319db7bc6e6e3b3faa80ddfac46a587dc",
     "fe48f488dfa3ec0889581da6d6cda878b7b5050674dd819b633224e36ad66382", 29540),
    (ROOT / "source_archives" / "development" / "ci_facility_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_facility_assessment_smoke.py",
     "a50259fd54ec98f4a0894e3ec570e81084430f7620b746ebcbf66b6f363140d3",
     "d645f00386f9fa5eb474d8dbb35a8fc689ab0de09e2b56804870d9c0ed77cbe0", 13517),
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
    print(f"reconstructed {target.relative_to(ROOT)} {target_sha}")
