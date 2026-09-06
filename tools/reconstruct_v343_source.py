#!/usr/bin/env python3
"""Deterministically reconstruct the governed SalCAPA v3.43 runtime source."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];ARCHIVE=ROOT/"source_archives"/"v3.43"
manifest=json.loads((ARCHIVE/"manifest.json").read_text(encoding="utf-8"));snapshot_bytes=(ARCHIVE/"snapshot.json").read_bytes()
if len(snapshot_bytes)!=manifest["snapshot_size_bytes"]: raise SystemExit("Invalid v3.43 source snapshot size")
if hashlib.sha256(snapshot_bytes).hexdigest()!=manifest["snapshot_sha256"]: raise SystemExit("Invalid v3.43 source snapshot digest")
snapshot=json.loads(snapshot_bytes.decode("utf-8"))
if snapshot.get("format")!="salcapa-source-snapshot-v1" or snapshot.get("version")!="3.43.0": raise SystemExit("Unsupported v3.43 source snapshot contract")
for relative,metadata in manifest["files"].items():
 content=snapshot.get("files",{}).get(relative)
 if not isinstance(content,str): raise SystemExit(f"Missing v3.43 snapshot content: {relative}")
 data=content.encode("utf-8")
 if len(data)!=metadata["target_size_bytes"] or hashlib.sha256(data).hexdigest()!=metadata["target_sha256"]: raise SystemExit(f"Invalid v3.43 target in snapshot: {relative}")
for relative,content in snapshot["files"].items():
 path=ROOT/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding="utf-8");print(f"reconstructed {relative} {manifest['files'][relative]['target_sha256']}")
