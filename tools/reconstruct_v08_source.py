#!/usr/bin/env python3
import base64,gzip,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; ARCH=ROOT/'source_archives'/'v0.8'; manifest=json.loads((ARCH/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    encoded=''.join((ARCH/name).read_text().strip() for name in meta['chunks'])
    gz=base64.b64decode(encoded)
    if hashlib.sha256(gz).hexdigest()!=meta['archive_sha256']: raise SystemExit(f'Archive SHA-256 mismatch for {rel}')
    data=gzip.decompress(gz)
    if hashlib.sha256(data).hexdigest()!=meta['sha256']: raise SystemExit(f'Source SHA-256 mismatch for {rel}')
    dest=ROOT/rel; dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(data)
    print(f'reconstructed {rel} {meta["sha256"]}')
