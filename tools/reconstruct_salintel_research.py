#!/usr/bin/env python3
"""Reconstruct reviewed Issue #151 Chat-led research sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_research.py.gz",
     ROOT / "salintel_research.py",
     "6b69967d324b8c2b4e18e9456c3c075a4e6754eb0ed5dcf53112341802ae0011",
     "3031a97f28359124dbced9ef234c1f961bbea9c4deff975335693aef34999b4e", 30001),
    (ROOT / "source_archives" / "development" / "ci_salintel_research_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_research_smoke.py",
     "bc1643edbbe6685fa7aadf1cda779c3a37b9919aaeecef58a47f508b8f3fe3e3",
     "cbde810222ec1e080074895cadcf235bf44ac0679a3eaa89e45383ee570ff7d2", 13559),
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
