#!/usr/bin/env python3
"""Reconstruct reviewed Issue #151 Chat-led research sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_research.py.gz",
     ROOT / "salintel_research.py",
     "64e59a9bf791977e227d173b6316c85d90dc585c000390c6cfef5796b4e36c95",
     "35938bfb53cdf86616d66ef4e290f986a6b619338e297fb7e4559c00dd8ea386", 45105),
    (ROOT / "source_archives" / "development" / "ci_salintel_research_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_research_smoke.py",
     "3a42d319b79518332afafba051b7a1039ea79de337c7d346f2395dba8e5468b8",
     "4fd667435a85feaafa8e4cbf477648cce131a445376bcf8403a9de139a444a69", 16621),
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
