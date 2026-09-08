#!/usr/bin/env python3
"""Reconstruct reviewed Issue #162 development sources from compact artifacts."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives" / "development" / "salops_preparedness.py.gz",
        ROOT / "salops_preparedness.py",
        "bbd956731254a0c47832d8d1873b3925009a48ea959addd25d8d5cb43dfe4a0a",
        "7f0ad35ef3510f98ae1ac5580faff887315fb1a606ab251e33c4e2e933904c40",
        76765,
    ),
    (
        ROOT / "source_archives" / "development" / "ci_salops_preparedness_smoke.py.gz",
        ROOT / "tools" / "ci_salops_preparedness_smoke.py",
        "2103f49c2ee2ee76edd135ff906591f9a48db5daacaa7a98b924efe96f3ca6b4",
        "fa51ed4e2cdfc2f385ebba6ca4a03475ef5e1d8cb32a39b8b348bb522d0e90b4",
        13134,
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
    print(f"reconstructed {target.relative_to(ROOT)} {target_sha}")
