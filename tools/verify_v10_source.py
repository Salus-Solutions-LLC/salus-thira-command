#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_archives'/'v1.0'/'manifest.json').read_text(encoding='utf-8'))
for rel,meta in manifest['files'].items():
    p=ROOT/rel
    if not p.is_file(): raise SystemExit(f'Missing {rel}; run tools/reconstruct_v10_source.py')
    data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    if len(data)!=meta['target_size_bytes']: raise SystemExit(f'Size mismatch for {rel}')
    if digest!=meta['target_sha256']: raise SystemExit(f'SHA-256 mismatch for {rel}: {digest} != {meta["target_sha256"]}')
    print(f'verified {rel} {digest}')
