#!/usr/bin/env python3
"""Reconstruct reviewed Issue #149 Personnel Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "personnel_assessment.py.gz",
     ROOT / "personnel_assessment.py",
     "486aaf9243984b0c0514dfa7872e5a9b1540b32ecd93007913ef2fcac4e8ba6e", "023206670c1a9de9192f5e49a68627e6f82e8284aa6501157d14ee472a9c7eef", 28405),
    (ROOT / "source_archives" / "development" / "ci_personnel_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_personnel_assessment_smoke.py",
     "d168bc30eb80e49e7cd57282f3885d06303a038b7188a0dd690b237926d08fb2", "5235767e00995306f739646449e942187a56dc62c85bd040d0c200d62e5cb0bf", 11499),
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
