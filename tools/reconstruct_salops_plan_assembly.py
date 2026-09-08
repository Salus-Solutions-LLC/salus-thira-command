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
        "dd5a6b922f2491c9d07bd0d9ef5662c0396eef999cf1d1e1ab5801ce4561959c",
        "984e662b061ac844e22ad52ea04420a4f4b1db100260178de33f3ecf15ea168d",
        176439,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "46f49e95aad18d027de9b2cc5457fe42fda4fc011943c4eda16237b26ddf4543",
        "fccee7aa26886e181dac2b6891871877b54804cd19a9a787951a2fe491d8c934",
        47839,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "9a42980a59601565c7d4cad65d663d94ff2b911a101ce2b88e27ece38a98c1f0",
        "e23a2eff161be95f4984b7b904d6511afb5d6bf51ba8d722eb25fcebb18b4f6e",
        48243,
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
        "f559b03c6b89e1fdeefc969f79e3cd95502394ced83e3af59f56e7e6e8083726",
        "8041d0f188bca13c7bac3a41c73da8bd997197e378d988e6c601af814ab4457a",
        6502,
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
