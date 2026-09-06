#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; manifest=json.loads((ROOT/'source_archives'/'v3.33'/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    path=ROOT/rel
    if not path.is_file(): raise SystemExit(f'Missing reconstructed v3.33 source: {rel}')
    data=path.read_bytes(); actual=hashlib.sha256(data).hexdigest()
    if len(data)!=meta['target_size_bytes'] or actual!=meta['target_sha256']: raise SystemExit(f'v3.33 source verification failed: {rel}')
    print(f'verified {rel} {actual}')
