#!/usr/bin/env python3
"""Reconstruct reviewed Issue #149 Personnel Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "personnel_assessment.py.gz",
     ROOT / "personnel_assessment.py",
     "8aabd5859939924ff009b81a3c68be892ae2e07b2ee533b69490a9cc27a4a660", "53a1c7f6ab6ad41d2bea034c2ceedba55a5efb61f7923b96701d6214f7efd6f9", 33601),
    (ROOT / "source_archives" / "development" / "ci_personnel_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_personnel_assessment_smoke.py",
     "3686557d0cdb9fc547af9c87e5e5e32d1790978ba6dc246fa8d8891db795bc8f", "6a960399f5ccc20baa6c05bd06571dc9cc6539d9b200e2cfc76cb80d1362d639", 15726),
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
