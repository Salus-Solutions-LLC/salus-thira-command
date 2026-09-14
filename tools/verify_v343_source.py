#!/usr/bin/env python3
"""Verify exact SalCAPA v3.43 runtime source and governed source overlays."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "v3.43"
manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
snapshot = (ARCHIVE / "snapshot.json").read_bytes()

if len(snapshot) != manifest["snapshot_size_bytes"]:
    raise SystemExit("v3.43 source snapshot size mismatch")
if hashlib.sha256(snapshot).hexdigest() != manifest["snapshot_sha256"]:
    raise SystemExit("v3.43 source snapshot digest mismatch")

overlays = {}
for overlay_path in sorted((ARCHIVE / "overlays").glob("*/manifest.json")):
    overlay = json.loads(overlay_path.read_text(encoding="utf-8"))
    if overlay.get("format") != "salcapa-source-overlay-v1" or overlay.get("version") != "3.43.0":
        raise SystemExit(f"Unsupported v3.43 source overlay: {overlay_path}")
    for relative, metadata in overlay.get("files", {}).items():
        if relative in overlays:
            raise SystemExit(f"Duplicate v3.43 source overlay target: {relative}")
        overlays[relative] = metadata

for relative, metadata in manifest["files"].items():
    if relative in overlays:
        continue
    path = ROOT / relative
    if not path.is_file():
        raise SystemExit(f"Missing reconstructed v3.43 source: {relative}")
    data = path.read_bytes()
    if len(data) != metadata["target_size_bytes"] or hashlib.sha256(data).hexdigest() != metadata["target_sha256"]:
        raise SystemExit(f"v3.43 source verification failed: {relative}")
    print(f"verified {relative} {metadata['target_sha256']}")

for relative, metadata in overlays.items():
    archive_path = ROOT / metadata["source_path"]
    target_path = ROOT / relative
    if not archive_path.is_file() or not target_path.is_file():
        raise SystemExit(f"Missing v3.43 source overlay or target: {relative}")
    archived = archive_path.read_bytes()
    target = target_path.read_bytes()
    digest = hashlib.sha256(archived).hexdigest()
    if len(archived) != metadata["target_size_bytes"] or digest != metadata["target_sha256"]:
        raise SystemExit(f"Invalid v3.43 source overlay archive: {relative}")
    if target != archived:
        raise SystemExit(f"v3.43 source overlay verification failed: {relative}")
    print(f"verified overlay {relative} {digest}")
