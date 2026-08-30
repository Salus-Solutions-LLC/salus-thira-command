#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];manifest=json.loads((ROOT/'source_archives'/'v1.6'/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
 p=ROOT/rel
 if not p.is_file() or p.stat().st_size!=meta['target_size_bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['target_sha256']: raise SystemExit(f'v1.6 source verification failed: {rel}')
 print(f'verified {rel} {meta["target_sha256"]}')
