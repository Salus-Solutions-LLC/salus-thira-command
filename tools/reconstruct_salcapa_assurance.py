#!/usr/bin/env python3
"""Reconstruct reviewed Issue #180 PROVE sources from compact artifacts."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_assurance.py.gz",
        ROOT / "salcapa_assurance.py",
        "173c6e461765f900540a33dc516e570915553fc78dc388c142b8835d42c0934b",
        "8899aa089fdb1ff63026955540e71ae57c61daf543dc0dc83117dfc7d36fd93b",
        15121,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_assurance_smoke.py.gz",
        ROOT / "tools/ci_salcapa_assurance_smoke.py",
        "522e2ec09d9b3d3a7abbd2f131b3a9a7c2aa4299c3bcb0072ba5642125f93c0b",
        "4a96187837515b543e65e2dfa14e7cc5d4109166f4722603920e36b9c610beda",
        5670,
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
print("SALCAPA_ASSURANCE_RECONSTRUCTION_PASS")
