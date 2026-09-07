#!/usr/bin/env python3
"""Reconstruct reviewed Issue #149 Personnel Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "personnel_assessment.py.gz",
     ROOT / "personnel_assessment.py",
     "99da11dd5e3a60db99959a69dc1af7f988112fdecf89a9e44efe69439241756f", "79e293aeef8f79cba38a4f7fbdab1a40b744a8e4ef422a60c57818739f0d5fc4", 37514),
    (ROOT / "source_archives" / "development" / "ci_personnel_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_personnel_assessment_smoke.py",
     "1d2aa9a826b1daed3926dc0cb98e6183c042ecf7b198586aa9239b7dfeaaada7", "17f16e680ff27fbcfa2d21d81b08a81fe3b39dbaf70dc98904df3ad34bf5ac7c", 20679),
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
