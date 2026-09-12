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
        "015e5a12080e3871ae8f3d3e1f1895d60037fb7e2da561262730538e1f6e9fac",
        "2681490e707bf26a9beeeaf5317bf75dc5a6a9b4ebb8814b08d178108852fae7",
        32780,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_facility_imagery_smoke.py.gz",
        ROOT / "tools/ci_salcapa_facility_imagery_smoke.py",
        "9ff44ae3b9360a50f1abda1ca9f72908bc7c96b2b56693304b488479250045ab",
        "1f434105b40b3b6829bdb19016907e4268c985b4e69a315371958eb11b37dfca",
        9716,
    ),
    (
        ROOT / "source_archives/development/salcapa-facility-imagery.js.gz",
        ROOT / "static/salcapa-facility-imagery.js",
        "4cf929bc2cccfdfaebc2269547d3c176699c281b11d32198eb68a53c0bf483f0",
        "69e81bed2beff537b135f07de602f9bd58f44e5757695e0f38b32678c0ef486a",
        7134,
    ),
    (
        ROOT / "source_archives/development/salcapa-facility-imagery.css.gz",
        ROOT / "static/salcapa-facility-imagery.css",
        "f8e72b28a662ca356c1adf91973b5723350ddba36140af154b92d47c0506f747",
        "e88b44ef27c9e06048778831bdd37a8856d1eb987607e148e216efab4674fc5e",
        771,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_facility_imagery_ui_smoke.py.gz",
        ROOT / "tools/ci_salcapa_facility_imagery_ui_smoke.py",
        "73a789d7e30039f0f13ef007aaf49ed65680aa922336cc7ec6a1a9c0d89e82f8",
        "6cc0cbe2d7538922ee1a502b0cf2f7cb446e731264e4e65dd8c1d2291023ee65",
        2872,
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
