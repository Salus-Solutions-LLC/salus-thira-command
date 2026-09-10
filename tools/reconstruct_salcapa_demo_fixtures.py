#!/usr/bin/env python3
"""Reconstruct the reviewed Issue #124 demonstration fixture source."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "development" / "salcapa_demo_fixtures.py.gz"
TARGET = ROOT / "salcapa_demo_fixtures.py"
ARCHIVE_SHA256 = "9b942823e4a150f7be873c23f4d9e32a65185ce915dc9297be6b1392205a0a14"
TARGET_SHA256 = "a640026236c68805d4b1104f864b4edca6f97f35bbfcbf63f7ab3d81c724e684"
TARGET_SIZE = 31133

compressed = ARCHIVE.read_bytes()
if hashlib.sha256(compressed).hexdigest() != ARCHIVE_SHA256:
    raise SystemExit("Invalid source artifact digest: salcapa_demo_fixtures.py.gz")
content = gzip.decompress(compressed)
if len(content) != TARGET_SIZE or hashlib.sha256(content).hexdigest() != TARGET_SHA256:
    raise SystemExit("Invalid reconstructed source: salcapa_demo_fixtures.py")
TARGET.write_bytes(content)
print("SALCAPA_DEMO_FIXTURE_RECONSTRUCTION_PASS")
