#!/usr/bin/env python3
"""Reconstruct reviewed Issue #180 PROVE sources from compact artifacts."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_assurance.py.gz",
        ROOT / "salcapa_assurance.py",
        "2c3ed02ad52943ffa6d58476809ad351071a671ac7fd855da7a447b944fd950c",
        "c1c6495d94892e49ce3ac9af1ef598ce41be6b1b32c7ad861931ff99ef774837",
        38556,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_assurance_smoke.py.gz",
        ROOT / "tools/ci_salcapa_assurance_smoke.py",
        "f2fb6402b47de11ec174839f6ccfc8a16742a2617103f45a27412242e7524680",
        "e65eba15718c80cb0eb3bebed93f96dd56b39c4555a36a6441ac16b6041f3c06",
        15556,
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
print("SALCAPA_ASSURANCE_RECONSTRUCTION_PASS")
