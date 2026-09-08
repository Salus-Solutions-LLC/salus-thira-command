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
        "5904d821c7dea1416a328c1e435be2ae21634ef1f21da07048ac15702ff53bfb",
        "e94b3d7cf8099bfb7fbc3da25ba3a0147272f5617e99714fe4a49f420b4fb946",
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
