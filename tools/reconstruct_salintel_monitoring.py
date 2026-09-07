#!/usr/bin/env python3
"""Reconstruct reviewed Issue #153 recurring-monitoring sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_monitoring.py.gz",
     ROOT / "salintel_monitoring.py",
     "9b8dd0750c9858ec771c7fce04951d8c138ca5c01f41e9586e2fe6100a59bb3c",
     "12b29f335329fa5f3622bb7f9dda469143bcd0040d14ab52bf900d28c4091cd1", 38654),
    (ROOT / "source_archives" / "development" / "ci_salintel_monitoring_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_monitoring_smoke.py",
     "7afd49b1d0829c95923c906deb9cbb479cabd0becb89dbd9b277d45aec3d7633",
     "aa87e47dd51b190b0f14368f53e0ae8abb070bbccf7bc60e6856ec63e3b4028e", 14945),
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
print("SALINTEL_MONITORING_RECONSTRUCTION_PASS")
