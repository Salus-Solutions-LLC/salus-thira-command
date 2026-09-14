#!/usr/bin/env python3
"""Verify exact SalCAPA v3.43 source against its immutable archive snapshot.

Verification reads the isolated archive-reference directory by default so current
runtime/UI source is never required to equal the historical v3.43 snapshot.
"""

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = REPO_ROOT / "source_archives" / "v3.43"
DEFAULT_ROOT = Path(tempfile.gettempdir()) / "salcapa-v343-reference"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--root",
    type=Path,
    default=DEFAULT_ROOT,
    help="isolated directory containing reconstructed v3.43 files",
)
args = parser.parse_args()
source_root = args.root.resolve()

manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
snapshot = (ARCHIVE / "snapshot.json").read_bytes()
if len(snapshot) != manifest["snapshot_size_bytes"]:
    raise SystemExit("v3.43 source snapshot size mismatch")
if hashlib.sha256(snapshot).hexdigest() != manifest["snapshot_sha256"]:
    raise SystemExit("v3.43 source snapshot digest mismatch")

for relative, metadata in manifest["files"].items():
    path = source_root / relative
    if not path.is_file():
        raise SystemExit(f"Missing reconstructed v3.43 source: {relative}")
    data = path.read_bytes()
    if len(data) != metadata["target_size_bytes"] or hashlib.sha256(data).hexdigest() != metadata["target_sha256"]:
        raise SystemExit(f"v3.43 source verification failed: {relative}")
    print(f"verified {relative} {metadata['target_sha256']}")
