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
        "b9886ae05a4453e0f33986d264743c78d05b9377953cfe456ef9aa541ac48834",
        "5a595d798fad8604b2aace0c4e70b23bbf99f8f903a159b87d69d0ecb41ab15e",
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
