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
        "bd411b45d4cd7d6202a84527f5700947e93e118874c653d818088accfba70810",
        "6ff447c6bd20592ed7a1f91cdeeab22cff376a2fbd46713aabe73dec8b557c00",
        53591,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "c6412f783525baf9e866222c3a5a6ec79b6030670030af08b9cda86dec390e06",
        "5f82ee48a00ec21d48bd136aa502eea3e419f2a32686e740e56870576e54ece2",
        17238,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "44af9990407acd79a4af989313bb004ce5e59907dcbc3a1f7cdd889591765b9a",
        "cf149280ec2d90a93215c837f87e6e5e4be8bfe991a973ff16109117a8a3b025",
        26898,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.css.gz",
        ROOT / "static/salops-plan-assembly.css",
        "8e8fb3e9206038e7ef2394cf096df89229a33f03f5520adb49f60b9bbbab385a",
        "da8b44a0841a0296ad62596295249fba6dd2d68b8e60104e597edb92ad07227b",
        2815,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_ui_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_ui_smoke.py",
        "83454bbdd9a96e5c1ef6d4925bb11f0e40bd726179a4007393bbfa5c894a7c47",
        "27f363b10dfcb1ab16fa5c16abc86ee582dcec351b40f6a6fe22e0481a442df9",
        3679,
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
