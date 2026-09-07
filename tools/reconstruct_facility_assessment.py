#!/usr/bin/env python3
"""Reconstruct reviewed Issue #150 Facility Assessment sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "facility_assessment.py.gz",
     ROOT / "facility_assessment.py",
     "797f630117955194cc5cb433a4fbc3ee98348242378df7d131a62342aec9eb44",
     "f61366a61ce24f2062ac5e432f836a8660fc5730e23132d8d4d400c89022458b", 49924),
    (ROOT / "source_archives" / "development" / "ci_facility_assessment_smoke.py.gz",
     ROOT / "tools" / "ci_facility_assessment_smoke.py",
     "a3efc4e94c29a23897687d8f23d5d6206a8096cfff09d82438069798f64ee6a8",
     "7f3df74153f09dfda4b3dbabdbf89691de7328a2e4eaed3517422fcbca11a18f", 18975),
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
