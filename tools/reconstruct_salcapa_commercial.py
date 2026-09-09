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
        "71ef6bfe7d5f8c30d1ff88f1764d2300117e09c50fd451867dfb889863e30f67",
        "bb3877441b64ee48e5ea5aebc173a146782a78ab22d4d16a22163650adf14318",
        253500,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_commercial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_commercial_smoke.py",
        "30f6e634dc01603a93409e5b76487acd0f54fe8698401266f6b0dd7fb099caaf",
        "8a3b75e48b14b79c15f2120a6d5e71841095c725ac60fb841d4db7bce707bea4",
        66022,
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
