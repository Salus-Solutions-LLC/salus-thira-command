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
        "4b30ddffd2f18628e69d19783e9a13a7fd16a57c4b2c8e3accdb11353118e339",
        "1b47b6d08c4634c3aa7d5d499990bb927ba19638a14ba01d3688ac303b651930",
        210355,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "9c120afd8b6d35adad99c95b45743ef4792310d89620dcd1065f0f5816721f71",
        "d1c723b05f4902e935953059c4a57499e39207f9e939593e9b8f7f0f5ce94910",
        61971,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "ccda33d49398bb85857b2036b54a8da2f4e78d3fbc5844c1d5705252cc54aafd",
        "02e1ee390816e4276d0dcab125fcc8cec22eba2477302bc9202e80bf7ce14788",
        54442,
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
        "b464e56df978b3b6ba6b9b74669eb8b8ec8cf992f406e94b2b1a45b20138db41",
        "1ebfe05b67545a4e75d0af44de4ffda5f21f6d4904ad659386b536d3a0551559",
        7571,
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
