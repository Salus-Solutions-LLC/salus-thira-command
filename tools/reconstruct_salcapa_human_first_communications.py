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
        "811f4630d0ed5f7e06d28c7862d6455cb75afff6635aaf092e17358453be6445",
        "2e75d6990ae372c1eb383794f8843f18dc52ecd73f5d0b472cfd3a9b05bcf98f",
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
