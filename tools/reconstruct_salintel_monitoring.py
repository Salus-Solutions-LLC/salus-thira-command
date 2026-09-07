#!/usr/bin/env python3
"""Reconstruct reviewed Issue #153 recurring-monitoring sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_monitoring.py.gz",
     ROOT / "salintel_monitoring.py",
     "742cea4489cb4e35bed1fdcbcf3ca6e9cbb18cc1f4b4be9a18d28092b5b52d63",
     "ae3d36dafae5efe6e8a74226a32a1591605f626f859f46efd08c64e4d7af581c", 20196),
    (ROOT / "source_archives" / "development" / "ci_salintel_monitoring_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_monitoring_smoke.py",
     "b1b2b673415841fda5c9c8c18b6dcb8607bf5762ff2d744201bc28e72392b20b",
     "bf94dfbef92a93093a837900f4dcfae724722d0e80c4fde76037dd332a8dbf1b", 9474),
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
