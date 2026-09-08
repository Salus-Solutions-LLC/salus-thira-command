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
        "b37a7b06f0a3f942d60df715ff4d91d385c21531126af6b5d12d952a18093295",
        "1bc039381685b3e5c7e213188a27dc939117cb193fb5f66492e269f3ab4719e0",
        38565,
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
