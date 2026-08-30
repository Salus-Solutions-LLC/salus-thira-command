#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_archives'/'v1.4'/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    path=ROOT/rel
    if not path.is_file(): raise SystemExit(f'Missing source file: {rel}')
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=meta['target_sha256']: raise SystemExit(f'Source verification failed for {rel}: {digest} != {meta["target_sha256"]}')
    if path.stat().st_size!=meta['target_size_bytes']: raise SystemExit(f'Source size mismatch for {rel}')
    print(f'verified {rel} {digest}')
