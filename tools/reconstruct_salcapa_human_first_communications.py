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
        "71d47c84c96979c7bb5a593220adc360922655f2b648531106e32231d8ce5bbe",
        "3fb705ba296b9820c2f15145922b6f232dad4df77ba667b0f323241b6f70b1b2",
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
