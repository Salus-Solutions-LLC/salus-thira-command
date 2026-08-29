#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; manifest=json.loads((ROOT/'source_archives'/'v0.8'/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    p=ROOT/rel
    if not p.is_file(): raise SystemExit(f'Missing {rel}; run tools/reconstruct_v08_source.py')
    digest=hashlib.sha256(p.read_bytes()).hexdigest()
    if digest!=meta['sha256']: raise SystemExit(f'SHA-256 mismatch for {rel}: {digest} != {meta["sha256"]}')
    print(f'verified {rel} {digest}')
