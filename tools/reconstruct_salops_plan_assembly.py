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
        "c12c836bdcd6454bcce45c4f3f8394848f5f8fcd011a020a39b14eea0bc370d4",
        "954d400d2733252c2d121a4c2ca59b5475e538322cfd9d9188f6895960538be9",
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
        "cda0a686ac43cbfa788da3457a802e2143a2bd5ce6cec5579d51bcf07ee11182",
        "ef01bf8bdbe3ede85428c2202b0cc9469447a5a17f9059efb1c65d909ce37b08",
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
