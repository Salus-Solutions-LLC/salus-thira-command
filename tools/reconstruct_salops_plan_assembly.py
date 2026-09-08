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
        "a96a6381c4da7b32a7dae6e70c321625821249dc48ba995ae29eb32662236a4b",
        "148ee4a24e59ab40512ae33d933ae280666bc538d4e6c1a4f1e50d69120054fa",
        212755,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "0e4b9d3732a7b9bb3771ee083acfdb16dfe505cdd2e492ef89a55150b3a24db5",
        "8317a5bb64efa990d8b23fbddaaeb3e04aff407642b8e52d9efc859a6d84e63f",
        65231,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "0278099baa8a82835b29a828dc968a2297dc06b7b39a97fbae2447eabe575f10",
        "9c639e05c8c39645ce419ea7f51ce6f71e2d6e734fe25517f9fb3baf118cd91d",
        56624,
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
        "29410213276f09748108b813d50f82f2ef55f0dfe88402e8c5c6b29d38b2f2c5",
        "1a8eef6235a8b84b127f0c53f8b4436918eef1ea0d67f691baf24d11fb4e92e1",
        7994,
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
