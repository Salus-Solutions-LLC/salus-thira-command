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
        "aeb53062e97e87a42c2c3149d1c97a3b2b1c4047ede121dabbfa8658ecd25c20",
        "803ad3fc85a7a4be0038869ff8bf94aefa262b60853a24f586fdce73d3c8778b",
        71715,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "0d9e8ab6a274726b062a52e2ed111acbf78e6ee47a45b672c73a867974078cee",
        "1d3cbc4afc47aaebff3d4b769f947887045d51b9fba50257ab6ed9eed1f848f8",
        20888,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "9f10b936cd13f2966ec9091821c262b3ca849f4f85e777eff6bed0e9a9185345",
        "4e6807eed84b8432d3e55c1d022b276944506c2def9211b599566c751ba1a3e6",
        30853,
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
        "b560aa257c167c502e673beec3c6c7c854f696127accda8608090d6ecac22414",
        "635f98e6b711241ca765495a7b21ede5c5eb9984d51c6dcd71a3922ed4dba467",
        3918,
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
