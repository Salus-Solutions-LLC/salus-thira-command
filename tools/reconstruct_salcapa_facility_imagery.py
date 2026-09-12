#!/usr/bin/env python3
"""Reconstruct reviewed Issue #236 facility-imagery relationship sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_facility_imagery.py.gz",
        ROOT / "salcapa_facility_imagery.py",
        "fbdc9e40c770af8690d7646261ca7f867db3d897ab1223ebd31c130045f90780",
        "d8a171329d6eedd871d24411bc738104515252828663ade645e2063f96de9186",
        32673,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_facility_imagery_smoke.py.gz",
        ROOT / "tools/ci_salcapa_facility_imagery_smoke.py",
        "9ff44ae3b9360a50f1abda1ca9f72908bc7c96b2b56693304b488479250045ab",
        "1f434105b40b3b6829bdb19016907e4268c985b4e69a315371958eb11b37dfca",
        9716,
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
print("SALCAPA_FACILITY_IMAGERY_RECONSTRUCTION_PASS")
