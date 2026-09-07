#!/usr/bin/env python3
"""Reconstruct reviewed Issue #146 SalINTEL relationship sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_relationships.py.gz",
     ROOT / "salintel_relationships.py",
     "c6990e4b2a9d7374f806e74d3ef0a2d7677ca01a7754eb6d92bfed2f3efbc2e4",
     "e263397133d8aee6d9e4720f649fdada69a1d70e0ff39d52c702e9640a0e17f2", 23938),
    (ROOT / "source_archives" / "development" / "ci_salintel_relationships_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_relationships_smoke.py",
     "9264b87b63fca2d0e6491458475d273b07bcff1720a839a74dcdd4a194f0c351",
     "dc1f9dde418159471cbd9368d4b81b6f119e91a57ca8a3f549cc707f0e81a42a", 12910),
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
