#!/usr/bin/env python3
"""Reconstruct the reviewed Issue #124 demonstration fixture source."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "development" / "salcapa_demo_fixtures.py.gz"
TARGET = ROOT / "salcapa_demo_fixtures.py"
ARCHIVE_SHA256 = "f16ce9b42dddf091c662413fa9cf8794175b3844b457cc595d7d3e708ecd6a60"
TARGET_SHA256 = "aa5ff54313bf81b49e43d7b18696cc944aa3b60eed20a2d188f1ff90645dc5fb"
TARGET_SIZE = 31240

compressed = ARCHIVE.read_bytes()
if hashlib.sha256(compressed).hexdigest() != ARCHIVE_SHA256:
    raise SystemExit("Invalid source artifact digest: salcapa_demo_fixtures.py.gz")
content = gzip.decompress(compressed)
if len(content) != TARGET_SIZE or hashlib.sha256(content).hexdigest() != TARGET_SHA256:
    raise SystemExit("Invalid reconstructed source: salcapa_demo_fixtures.py")
TARGET.write_bytes(content)
print("SALCAPA_DEMO_FIXTURE_RECONSTRUCTION_PASS")
