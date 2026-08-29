#!/usr/bin/env python3
import base64,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'v0.7'
manifest=json.loads((ARCH/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    encoded=''.join((ARCH/name).read_text().strip() for name in meta['chunks'])
    compressed=base64.b64decode(encoded)
    if hashlib.sha256(compressed).hexdigest()!=meta['archive_sha256']:
        raise SystemExit(f'Archive hash mismatch for {rel}')
    data=gzip.decompress(compressed)
    if hashlib.sha256(data).hexdigest()!=meta['sha256']:
        raise SystemExit(f'Source hash mismatch for {rel}')
    path=ROOT/rel; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
    print(f'Reconstructed {rel} ({len(data)} bytes)')
