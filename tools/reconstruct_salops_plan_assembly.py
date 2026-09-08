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
        "66772ce65bc9f64152e78eef85f25cbbd13a6f5afd4f3a62b7f7cef3514fc030",
        "098a2bb49c99e5cce9792bee6f095dd75cdeacbf6660054fccb91e75bec0fbed",
        207443,
    ),
    (
        ROOT / "source_archives/development/ci_salops_plan_assembly_smoke.py.gz",
        ROOT / "tools/ci_salops_plan_assembly_smoke.py",
        "7ac011e208035f9e08ab541b76cdeba7f6e21d7679cfee6a07ee3d1e03b7ce5b",
        "2009362e40500130d59d4a23d4060b064205bd35c4ce229677529ef481dab264",
        55801,
    ),
    (
        ROOT / "source_archives/development/salops-plan-assembly.js.gz",
        ROOT / "static/salops-plan-assembly.js",
        "9ac90461c65a6b649a63b87ca1e7b710007f5ceb2cba9bd3a08490a739024fd9",
        "45c724b3a3f4d0ae88c2d30b04bcbc2841f780779f3945be76a0c2207a911093",
        54031,
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
        "ab6fedb6b272bd3bf1c21d7f0628fdd44e9412999e3161e8fc521b6a1acbb279",
        "83aadb97a5c2fa60c237f6aa5457977674939a6c435f646f8c3b95d868f08393",
        7361,
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
