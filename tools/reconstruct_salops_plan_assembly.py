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
        "e6defd78e08c1cf383329ada130542313af49a5daa32f49660863601a8111231",
        "c752681b18133375321f2024509726ba986de4e53312174cca249609ab2542dc",
        204002,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "8f472c024edebf05a0d252a9b8d31903420c7053a9a7acd1ce01cb3a553567a0",
        "7a24c0f8a8cb85e09dc96496c81677dce31c7b4c5b3d27fc1aa1dbb84db62bad",
        54907,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "0188e55b488dcf4b895624ac73626454c8ba149dbd1e195864fdf3ad635bcdf8",
        "b42c3df4d00951167faa86ededefe8f2d3a3a961e9013af306aa0afc813d1b14",
        53130,
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
        "55a1dce6bc12528e12bbbe5f423f4f0eeb42ade30e8aac1cc1d96f5d79e3ecae",
        "87fcebeb96438f367b7ec95233726839b42523e1b1b4f9626220689219e0fef4",
        7175,
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
