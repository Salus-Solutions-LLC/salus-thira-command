#!/usr/bin/env python3
from pathlib import Path
import base64,gzip,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'v0.6'
manifest=json.loads((ARCH/'manifest.json').read_text())
for target,meta in manifest.items():
    enc=''.join((ARCH/name).read_text().strip() for name in meta['chunks'])
    raw=gzip.decompress(base64.b64decode(enc))
    digest=hashlib.sha256(raw).hexdigest()
    if digest!=meta['sha256']:
        raise SystemExit(f'Hash mismatch while reconstructing {target}: {digest}')
    path=ROOT/target; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(raw)
    print(f'reconstructed {target} {digest}')
