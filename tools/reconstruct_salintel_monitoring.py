#!/usr/bin/env python3
"""Reconstruct reviewed Issue #153 recurring-monitoring sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_monitoring.py.gz",
     ROOT / "salintel_monitoring.py",
     "ac98c4445908ceede3cc42be11a5ab17ecfe806eeb7d725449928b067ded4612",
     "3739007f15723547dfa3943cb2b2e643c24b7c2ebdc9cdb5997e4de30b63b1c5", 45828),
    (ROOT / "source_archives" / "development" / "ci_salintel_monitoring_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_monitoring_smoke.py",
     "054662dd0180950caaad08f993b589ab355dd2d13a7d5988b5d58f72843d5a24",
     "b4b596056c6c8c573ca75ffcd4b53e39734d61afdd1182bf2e19019d1ea0181e", 17783),
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
