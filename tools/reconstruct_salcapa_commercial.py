#!/usr/bin/env python3
"""Reconstruct reviewed Issue #154 commercial-planning sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_commercial.py.gz",
        ROOT / "salcapa_commercial.py",
        "ad0b33766bed46a74fb2dcd26e8f8d26195f2498cfa812cdaded510ff8855d1b",
        "50c0c48f309b46858f9d908624b15eac3e8d9f176a9e7d146eb28252aaadba43",
        201367,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_commercial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_commercial_smoke.py",
        "8109563c2dea05e60e482084b9ef99e0c5a777375ee67dd22b1f0b6f192ab522",
        "545280d3dcc6f7cffa63e0dcbf36fbbf65a3f624c091f7cbda405122a0c0e9de",
        57828,
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
print("SALCAPA_COMMERCIAL_RECONSTRUCTION_PASS")
