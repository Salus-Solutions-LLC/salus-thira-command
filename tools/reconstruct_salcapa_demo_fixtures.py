#!/usr/bin/env python3
"""Reconstruct the reviewed Issue #124 demonstration fixture source."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "development" / "salcapa_demo_fixtures.py.gz"
TARGET = ROOT / "salcapa_demo_fixtures.py"
ARCHIVE_SHA256 = "7280de84cfe8e83c2eb299039b3f70e6334a4503e5558faa7e1db1fbeb1e1e0a"
TARGET_SHA256 = "23b152fc2ab54bf0388feb162788e51cce9b2041a366ace3b1b16827e2d01a7e"
TARGET_SIZE = 15911

compressed = ARCHIVE.read_bytes()
if hashlib.sha256(compressed).hexdigest() != ARCHIVE_SHA256:
    raise SystemExit("Invalid source artifact digest: salcapa_demo_fixtures.py.gz")
content = gzip.decompress(compressed)
if len(content) != TARGET_SIZE or hashlib.sha256(content).hexdigest() != TARGET_SHA256:
    raise SystemExit("Invalid reconstructed source: salcapa_demo_fixtures.py")
TARGET.write_bytes(content)
print("SALCAPA_DEMO_FIXTURE_RECONSTRUCTION_PASS")
