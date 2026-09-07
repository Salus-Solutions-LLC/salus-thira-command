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
        "be514b553a1e53f8153f9e04c4a6d45a312c384458d03ea47ef499848587d58b",
        "39acf51fe749d9d4374fd833d4c49655b664b0822a38cb2c63941f8430bf0b30",
        16460,
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
        "bcb44a3a2b4af7d95828b5517bea678a408c897fd4a7f342630eb393531407df",
        "14061363b483e023d25fba41bb627728f0c512276b78c3ac7ba14482f77bf011",
        2214,
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
