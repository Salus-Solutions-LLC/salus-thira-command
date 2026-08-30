#!/usr/bin/env python3
import hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; M=json.loads((ROOT/'source_archives'/'v1.4'/'manifest.json').read_text())
errors=[]
for rel,meta in M['files'].items():
    p=ROOT/rel
    got=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ''
    if got!=meta['target_sha256']: errors.append(f'{rel}: expected {meta["target_sha256"]}, got {got or "missing"}')
    else: print(f'VERIFIED {rel} {got}')
if errors: raise SystemExit('v1.4 source verification failed:\n'+'\n'.join(errors))
print('V1.4_SOURCE_VERIFICATION_PASS')
