#!/usr/bin/env python3
"""Reconstruct reviewed Issue #154 commercial-planning sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_commercial.py.gz",
        ROOT / "salcapa_commercial.py",
        "5aa8fc8354e22ea52c42c9eb09cc8ab1299bdbfbc42c04c2c474a3c7216febcd",
        "76a78b67b8096d3d0fd0aa058c1e6d4e78830c4fcb3545f35ca588b4362ff6b8",
        89966,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_commercial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_commercial_smoke.py",
        "c4bad9f4e7fce365d0165e653971af58eb0e94f8af56ff66750f577fe0057137",
        "5b0453ab9970860320246831f1c110526a34a6c250672f5be3b7100794bfb5eb",
        25232,
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
print("SALCAPA_COMMERCIAL_RECONSTRUCTION_PASS")
