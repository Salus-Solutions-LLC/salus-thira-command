#!/usr/bin/env python3
"""Reconstruct reviewed Issue #184 autonomous planning sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salops_plan_assembly.py.gz",
        ROOT / "salops_plan_assembly.py",
        "8a8098e8590dcd047bad6e211d1097629118fd4df899117ce7764f5ef52d0db9",
        "c9ff1aff82bb4ba4d184a6509dfa157d5d87b92695bc357cd6ad3d597b7f70cc",
        151549,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "4afbbc68e84cbcf90caf648ddb1bc4c2f390ea03e537a7ffb970b2e239121251",
        "f2d12a94736ae129f8aede5751ca7f39352fd7f324588b7bcf44150a64945454",
        40898,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "c32c020d1c9e2b43f1419eb7801667f1c003e574193df30d4a1c0ab15b56ce15",
        "bc10c1310e7696ae64e6dbe20d58d5d86f4b5fc96a20e45b0d4648fc52118538",
        45374,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.css.gz",
        ROOT / "static/salops-plan-assembly.css",
        "fbeb0106b484da83ff31e35bc1fcb115ab4682e5b2b85e126d4b2ce844e6c89c",
        "8b18f4cee29850411226a069996bc90304f5bf03ec81e73eb3559459ebc6c58e",
        2940,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_ui_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_ui_smoke.py",
        "e3c96e92ef0ee008cba52577feda6d6486bf7a728af04de3b1cfea2a12f60a56",
        "a70eb0590caa3ba22c9f9b73b1ded3ac1384a9cbf2cb2bb2e1f8e5d9f8fecd43",
        5881,
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
print("SALOPS_PLAN_ASSEMBLY_RECONSTRUCTION_PASS")
