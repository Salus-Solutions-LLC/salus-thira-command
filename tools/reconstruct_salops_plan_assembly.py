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
        "bc428c7534f1b8413b5a9c771ab7ce66c0c307d28e5a08f8c22557dc7935be42",
        "76aa7b04939dc9b939a1d5ec72fb863559682d2ffffa86168db31d3b8fa555d1",
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
        "d332f3da674d9e02050c1fe752dd3b4ce955eafd96ca98a83112c534e60ef59c",
        "d58d7501fdbc8f4b655b351d636852e84e6dd5acdac88c7419a6cbfa65e0ca47",
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
