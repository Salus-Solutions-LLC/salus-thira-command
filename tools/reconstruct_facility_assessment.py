#!/usr/bin/env python3
"""Reconstruct reviewed Issue #150 Facility Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "facility_assessment.py.gz",
     ROOT / "facility_assessment.py",
     "04b9a2828c2215e2ab0d60d8cb8c71895cefb1c2c5b8a90a399baf91875e1012",
     "2fd60a5f988eb3bf133729f31a3f12bd1f49b3d9960ecb21363ddd0f7abce1e7", 42395),
    (ROOT / "source_archives" / "development" / "ci_facility_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_facility_assessment_smoke.py",
     "2d649c6f459e5c9f3db31429e39df2cd04f452877b7816a48f8315b9ac731655",
     "9e9ead704977aa1bc1181a4aed35307951301d08614f357b08b56e4445e221d3", 14517),
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
    print(f"reconstructed {target.relative_to(ROOT)} {target_sha}")
