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
        "9093383021e3bdb8f797703a8aeed1d036fa1cc3d5140b203c9bb4944a0223f6",
        "882297fa7c73845bb983e29e9a4fecf770cceae93d56a7b7a687ba9b493f06ea",
        16643,
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
        "2c42349ac000109a9fae6d659e8c5ae2fc2bd1e147d43cf9a34caa968da12765",
        "66c1ba6e64a34da7c9a245d97012e7b24aad888e94e1001c562db6c344174249",
        2448,
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
