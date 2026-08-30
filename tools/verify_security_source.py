#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_archives'/'security-codeql'/'manifest.json').read_text())
for rel,meta in manifest['files'].items():
    path=ROOT/rel
    digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ''
    if digest!=meta['target_sha256'] or path.stat().st_size!=meta['target_size_bytes']:
        raise SystemExit(f'Security source verification failed for {rel}')
    print(f'verified {rel} {digest}')
print('SECURITY_SOURCE_VERIFICATION_PASS')
