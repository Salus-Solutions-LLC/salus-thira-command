#!/usr/bin/env python3
"""Verify exact SalCAPA v3.40 runtime source and reconstruction snapshot."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "v3.40"
manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
snapshot = (ARCHIVE / "snapshot.json").read_bytes()
if len(snapshot) != manifest["snapshot_size_bytes"]:
    raise SystemExit("v3.40 source snapshot size mismatch")
if hashlib.sha256(snapshot).hexdigest() != manifest["snapshot_sha256"]:
    raise SystemExit("v3.40 source snapshot digest mismatch")
for relative, metadata in manifest["files"].items():
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing reconstructed v3.40 source: {relative}")
    data = path.read_bytes()
    if len(data) != metadata["target_size_bytes"] or hashlib.sha256(data).hexdigest() != metadata["target_sha256"]:
        raise SystemExit(f"v3.40 source verification failed: {relative}")
    print(f"verified {relative} {metadata['target_sha256']}")
