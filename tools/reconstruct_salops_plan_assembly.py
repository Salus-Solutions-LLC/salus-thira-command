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
        "2ec8af1758ed7f57bffe6e1c89bbd0645a561b789158b4988bacd76a8d8f8e19",
        "d4d7bfe0f7c9de6538d1cd70a57bfbe603c36e94612679a283b2bcb9511e00a6",
        130821,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "bb4fd491cb2df024325ef4bcee174aff92e2859eb947e342e58a4ebfdb056dea",
        "60b385137c482e740deb042215e6c58db77f3cf2c2c1071a99eb540ddc31c88e",
        35405,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "43aabc7c9e7da580d43c86c50418c9491ac1f625a5732d443565a276947fd064",
        "5462cb69235819ed8dd239e7f4c0b9690fdc186f8c81f1ba0b5a80e6fbd7cf90",
        43133,
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
        "c0ed11b22829a06c3116d3e196deb3fe6eb20c16da21356911facb2c6d11d960",
        "da14082a18bf195ce8b6e3ba335f2062a0a5d3a1f3d2ecdf5b3f1d941cd09431",
        5313,
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
