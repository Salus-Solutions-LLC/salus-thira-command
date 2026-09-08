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
        "19ded86d96a623409e77da7544e7af9fdec68733b3495e607b141495661271c1",
        "c5016224349db5984c0aba40c188c7b3d09cb3fc3940e605a5fd50659dd16c70",
        229523,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "e7d5aebba5ade4de8b62c53dfa0d63d2a048b32319a28e634c2e095aa00696d1",
        "8a50241edf22e18801a2ed9baa00687a5c900ccde907d6551593f48dc5f86591",
        69961,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "596f413299892e7f35990066879a4d5328d682416889bf96baec466735888a51",
        "e7a1bcc20b763dd5625b56ba77daf17710e11e6b6bbc81c7fa428fd73855beb2",
        61025,
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
        "6c241504fc4a12efbc8d23b42c3cc7997a0454fa01557dffda8e632cbdb0598c",
        "674f56e835a2a8ec01e091650d1249e3003081a2d639cd39d8fadfb0b04740c2",
        9889,
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
