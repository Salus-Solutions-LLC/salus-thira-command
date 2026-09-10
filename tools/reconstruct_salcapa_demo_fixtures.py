#!/usr/bin/env python3
"""Reconstruct the reviewed Issue #124 demonstration fixture source."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "development" / "salcapa_demo_fixtures.py.gz"
TARGET = ROOT / "salcapa_demo_fixtures.py"
ARCHIVE_SHA256 = "c62724c4057b4d23ef168d3ee033088193394718c4da6724ff505d0fd6b6bfb1"
TARGET_SHA256 = "9e15f63ada7d0c974dfce3247a7cdf65fc2e77512a5f03712b7bffea4e5301b3"
TARGET_SIZE = 31992

compressed = ARCHIVE.read_bytes()
if hashlib.sha256(compressed).hexdigest() != ARCHIVE_SHA256:
    raise SystemExit("Invalid source artifact digest: salcapa_demo_fixtures.py.gz")
content = gzip.decompress(compressed)
if len(content) != TARGET_SIZE or hashlib.sha256(content).hexdigest() != TARGET_SHA256:
    raise SystemExit("Invalid reconstructed source: salcapa_demo_fixtures.py")
TARGET.write_bytes(content)
print("SALCAPA_DEMO_FIXTURE_RECONSTRUCTION_PASS")
