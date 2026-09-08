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
        "1fa865d90c42701a6522f21947855268907cd7bc1ef96939e75f3f08fd06b6ba",
        "81e3f7765b3cb893124a9351a435b7661bfd16ac6d6623509fb81f628fefe7ec",
        97154,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "9a94e6a4dcd832d501d69948f40e6d01635aec9a8621f2df987d33f98ebcfdf0",
        "1ca14a30cea4f72a2b51732faeef2bc2781b8dbea4c8ae476f2d6f8b8d3e8865",
        26023,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "c1f207901a970fccd3a0a817a32dda85e96e845a3688945772cb97931911e078",
        "3e197aea019ae3a32b61cf4ab595dbc8ef3bec3c7484a7c1d1f8697fb52c9760",
        35983,
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
        "c8fc3995421b1341776f1d850f12e1fec6ea56c126ecb52e056199e78a00d4fb",
        "de2650080a3488d71b12fe553a95b5c8b1e6238e1d44d2c3baaabb8631dfc946",
        4468,
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
