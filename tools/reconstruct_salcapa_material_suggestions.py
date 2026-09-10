#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 governed-source-suggestion sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_material_suggestions.py.gz",
        ROOT / "salcapa_material_suggestions.py",
        "8d8d395670a9065813c1b3eee4146ff8e5976c78609d1dca9830c639bb402655",
        "801da05f3201b6215f2bd271bea5c299d284008c1d9a67f1c68e5c8c1f6b0631",
        49972,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_material_suggestions_smoke.py.gz",
        ROOT / "tools/ci_salcapa_material_suggestions_smoke.py",
        "5b34dfa0d93c5d90df643a1e90459d2920cc48462c0eefedf00154e716253cd2",
        "6896768eb56b199ba61ae90cbca20c65ffe54e54361372e3b11982195c0fcca6",
        14381,
    ),
    (
        ROOT / "source_archives/development/salcapa-material-suggestions.js.gz",
        ROOT / "static/salcapa-material-suggestions.js",
        "c2812bde15fb38324febd5acd48143fdd35ae39f7f0a6f3b0d607d5fb244dda2",
        "fcb6568fcbc8cbc05581a3450cfb205b7d231d61ba6b943ff7a846a5a727714a",
        7522,
    ),
    (
        ROOT / "source_archives/development/salcapa-material-suggestions.css.gz",
        ROOT / "static/salcapa-material-suggestions.css",
        "8ea3e0437b7422f3e4977d692a3da3465035fb7d762b7e894986febeeeb77fae",
        "f83f3fc988cd97ba1e9e01d6e2c33732b817c4463091b27503d0c2001ffea734",
        493,
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
print("SALCAPA_MATERIAL_SUGGESTIONS_RECONSTRUCTION_PASS")
