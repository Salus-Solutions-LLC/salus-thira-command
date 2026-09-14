#!/usr/bin/env python3
"""Deterministically reconstruct SalCAPA v3.43 runtime source and governed overlays."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "source_archives" / "v3.43"
manifest = json.loads((ARCHIVE / "manifest.json").read_text(encoding="utf-8"))
snapshot_bytes = (ARCHIVE / "snapshot.json").read_bytes()

if len(snapshot_bytes) != manifest["snapshot_size_bytes"]:
    raise SystemExit("Invalid v3.43 source snapshot size")
if hashlib.sha256(snapshot_bytes).hexdigest() != manifest["snapshot_sha256"]:
    raise SystemExit("Invalid v3.43 source snapshot digest")
snapshot = json.loads(snapshot_bytes.decode("utf-8"))
if snapshot.get("format") != "salcapa-source-snapshot-v1" or snapshot.get("version") != "3.43.0":
    raise SystemExit("Unsupported v3.43 source snapshot contract")

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
    content = snapshot.get("files", {}).get(relative)
    if not isinstance(content, str):
        raise SystemExit(f"Missing v3.43 snapshot content: {relative}")
    data = content.encode("utf-8")
    if len(data) != metadata["target_size_bytes"] or hashlib.sha256(data).hexdigest() != metadata["target_sha256"]:
        raise SystemExit(f"Invalid v3.43 target in snapshot: {relative}")
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"reconstructed {relative} {metadata['target_sha256']}")

for relative, metadata in overlays.items():
    archive_path = ROOT / metadata["source_path"]
    data = archive_path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != metadata["target_size_bytes"] or digest != metadata["target_sha256"]:
        raise SystemExit(f"Invalid v3.43 source overlay archive: {relative}")
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    print(f"reconstructed overlay {relative} {digest}")
