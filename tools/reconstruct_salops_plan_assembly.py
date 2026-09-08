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
        "48e5f8853c16365bda6bb39d7583cbc9e0f395b13f232e7cd52d091422d999f1",
        "ffff74a313b165c4bc03f7d57304179b2037b43c2c3c831a9493de853625ddd6",
        227821,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "36e4dd10e3d9921a30594be23a346db901c9a10b982ac81524affc891bba78b0",
        "3bbd0b03af402826a5a93f39aa412d8bd4e279c83c1e6c51ab72d2bc24d42390",
        69961,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "c83a2362eb96090d5016aeec286f44f2a668fe39f1e7db2715e265b68a9289e3",
        "70b2a71ae18601b011fd91f995876d74b879a0f12d1c136a06f56253f298aea5",
        60910,
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
        "7f7260b464792f69044bb7c7b3d33663761edddf6fe7c4fdc9d12fbe1bd7719d",
        "dd9ffb1e3f03ed20bb9903baa6350e8e572e5149066a64df7e8e3de7856f7c50",
        8518,
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
