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
        "7efbe4c300eba27949716bdd7ed1e03832d648e1600916799a16b984622c0368",
        "7b7869a0a4cb6001db730caec2fab66f920922f2ab54e09e27e97914f635cc56",
        228588,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "c2af1db0d8ea1ae2aab4648143d0f5c4acfbbdfda88d47425c7f4182e3f0c1b6",
        "18eccd8a197ddf6082fb8d9265d65eb9872a3ac918c7b9ee294fb96a5218df63",
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
        "a006a007833c44fd5d96a16ffbd4486a8f0f6654b9a700e393e3748a9a197a1f",
        "ed446ad337e96536dc04424cab3a1415f63126b057f643c50e5094cbd0e90eb2",
        9193,
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
