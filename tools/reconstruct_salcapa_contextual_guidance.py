#!/usr/bin/env python3
"""Reconstruct reviewed Issue #125 contextual-guidance assets."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa-contextual-guidance.js.gz",
        ROOT / "static/salcapa-contextual-guidance.js",
        "f4d6c7f9106a7d36eb352da0b558ce4048832c144126b3a46c353458c6f77428",
        "a4408fcf445524ba0c884e2406857402a11a2bbc6e8bab2a4ab1c220256e8e52",
        23036,
    ),
    (
        ROOT / "source_archives/development/salcapa-contextual-guidance.css.gz",
        ROOT / "static/salcapa-contextual-guidance.css",
        "46dff681be8a03e58a0b7a36b05b04106f842a31a7690a5eedff5cf3f97ef0b3",
        "8f0b1a889c40fbd6fc342db305972555f466292d11365541455bbf7c9f3e8963",
        2300,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_contextual_guidance_smoke.py.gz",
        ROOT / "tools/ci_salcapa_contextual_guidance_smoke.py",
        "0b011d08f1f7345fb42ff551dda7f9e0aa4a7d02711845136ffa2802114aabe0",
        "55d5f6933b5a63bb66485a70d00ae6e1d00a7d4fc7ad96eace5897f6c58d958f",
        3790,
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
print("SALCAPA_CONTEXTUAL_GUIDANCE_RECONSTRUCTION_PASS")
