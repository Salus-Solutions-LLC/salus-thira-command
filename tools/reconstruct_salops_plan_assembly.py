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
        "7f3a9ba0869286d6aa76ae8c349d32da44cc77227c5b1fb8b9ea837988e0ea03",
        "c424d58995deb42963e542e35f815c6e011c39ea445f3cbbc6a22227bb006d0a",
        110493,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "0addadd544953928ad2b9c89afb2e657c93b7fa53f3ae2a680c64672e03b2fdc",
        "9bca810b61c68eacb568ed37a0eab8e06a956fe87fc89363f83a4ca4cdfa5b4e",
        29738,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "5871273b6659761defd664946dbe32b0ac8c5f6530c180cc97052fc7d8299454",
        "98dd43ba2c0dde2dd8f7eaeda1b46d037dcc35e24559727af91143ed53cd6d80",
        37187,
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
        "d23bf2b7d2ed529b8e4354c1f534b58e64a392bd257861465342543b69795871",
        "5d847bd86961c51fc837c81aa3304901dae4189fa507b01955c46e136e315413",
        4688,
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
