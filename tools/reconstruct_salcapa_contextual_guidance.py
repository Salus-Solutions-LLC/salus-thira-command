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
        "9fb063f5859577d1ef8abf3c4d77bc215c2bd4d90647eeb6a2806e54c220f50b",
        "0fea03ce1fa911432cd11d21cca6f775c6ab2b4814036c97c757c0482de47ebb",
        23414,
    ),
    (
        ROOT / "source_archives/development/salcapa-contextual-guidance.css.gz",
        ROOT / "static/salcapa-contextual-guidance.css",
        "bf0c5eef0de03c4b0e82bbcab107da8b1b3450ec8a30143d1c409b0085516582",
        "a1468e25d875e004c5df60064b43f8c157dc7a3e9b61843355076702ad6bcda0",
        2645,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_contextual_guidance_smoke.py.gz",
        ROOT / "tools/ci_salcapa_contextual_guidance_smoke.py",
        "a2dd409d349846c27777a2c62526a23847d46303871ba8257fc3ef830fba5021",
        "eba027a909ba499adf6c35ddb21c52c411a3ef489295216d3a1984509bb4cb64",
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
