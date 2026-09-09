#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 material-processing sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_material_processing.py.gz",
        ROOT / "salcapa_material_processing.py",
        "f81e2079e09b2bf9d3197f8ad6ed1ba2b2161925754ccf233e724e092f6e8515",
        "333a3870fedbbbdd527fe07ceb7b3d4de2dd27662e53f795019786633ea45f2f",
        29150,
    ),
    (
        ROOT / "source_archives/development/salcapa-material-review.js.gz",
        ROOT / "static/salcapa-material-review.js",
        "5b60abc263c0b879954c7332bdedbca8e3c925b9f2b9d4ca7044f854fb1069ad",
        "5f5dcaefe55a79cbf3b59a88859d608fcb4a8ffdf8be5152ab7823b1a0317503",
        5864,
    ),
    (
        ROOT / "source_archives/development/salcapa-material-review.css.gz",
        ROOT / "static/salcapa-material-review.css",
        "959bd44e3f8bc5a36dd9aabbaa6d60080b7992bb097d0b53f962770eef455afd",
        "ee30591f4c393d1339f62decd786137d105aeb55b7141ce3f8df87887e1985cb",
        1081,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_material_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_material_processing_smoke.py",
        "8e4dcde84131103267f72cc43bae7eb4ab5f19e5f733b11338e4b8721dd87a82",
        "f02eb6a439463657ccc3beed2bf2febd0b3a776be932dd23ed8c7b2e500dd4bc",
        8162,
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
print("SALCAPA_MATERIAL_PROCESSING_RECONSTRUCTION_PASS")
