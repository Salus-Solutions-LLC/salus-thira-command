#!/usr/bin/env python3
"""Verify exact SalCAPA v3.43 source against its immutable archive snapshot.

Current-runtime validation should pass --root pointing to an isolated reconstructed
reference directory. The repository root remains the default only for historical
explicit verification workflows.
"""

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = REPO_ROOT / "source_archives" / "v3.43"

parser = argparse.ArgumentParser()
parser.add_argument(
    "--root",
    type=Path,
    default=REPO_ROOT,
    help="directory containing reconstructed v3.43 files (default: repository root)",
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
