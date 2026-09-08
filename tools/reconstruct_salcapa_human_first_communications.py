#!/usr/bin/env python3
"""Reconstruct reviewed Issue #204 human-first communications acceptance source."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/ci_salcapa_human_first_communications_smoke.py.gz",
        ROOT / "tools/ci_salcapa_human_first_communications_smoke.py",
        "74e234c480b81f7270b25b912b1f45aac305766e2a81a86c1bcd98e246b37599",
        "044cc3d7977a3254b67fe826f835a6a4f25978f7dab8c6966efd361114cb2c24",
        3421,
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
print("SALCAPA_HUMAN_FIRST_COMMUNICATIONS_RECONSTRUCTION_PASS")
