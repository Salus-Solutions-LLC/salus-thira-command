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
        "1482e71dea260d867426f4dcdd7c5b39e15858b4b9ea0ac75a4a216212b43ebc",
        "b4f79db95d94ae7d81b073226c48b365d80320c314d991e73ff72abaafe9f43d",
        173460,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "7eda145e348b1952cc2cd5af98f234f4bf68caac186be1439096e07bad5821d9",
        "58b58ac72bd8262b835955a143586d96a0a0fe41a159174b8931f1460094160a",
        45822,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "74bc326dc66fecdecf5a76ad585a2c53fb17144b912e98f3727a7c80a0089824",
        "9a3e1964abf7fd8ad84a18677db3eb2af61455eac994b28e73574aa989b10d89",
        47740,
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
        "aaee60845ac8fa65bc02fb12d88894171a9f496c0454d8ec3771854d27de1049",
        "319ec1719d21e65ec0132972f55c2fc689b17809d1f64ee3dad3f72673444c59",
        6366,
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
