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
        "7b07b2b2dc34ca612fb36af974303a5c2cf2138ceea53f3df0d84d39730e2599",
        "609cacd2bee1cbb5d94581e4a89c62416af280785f2c72d8f349d37d563297a8",
        208781,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "23349355603054ea6b78d30faaedb6db6cebdc36d29be201630ea3d2e3be26db",
        "28f324750db51dcb93bbeabecf7093082e0831832505c1fe950c3e752b136f24",
        59467,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "d1a0e70ab166a4a8357ed7a4ba79ae9f51db8d01f8605e7a981d492926838d22",
        "d09015a2a52e2868ebece0f3e7770b045a6d111d295f013394a3affb463a5f5f",
        54404,
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
        "5b359e8964ee1484954e5aea34c46913e3287eb8fe503bf3770aa372769aa7e3",
        "7813579d8478dd8c911d8d6a880a64d0d4f475e0652eb2279f483c6a50978763",
        7515,
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
