#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_archives'/'v0.7'/'manifest.json').read_text())
ok=True
for rel,meta in manifest['files'].items():
    path=ROOT/rel
    if not path.is_file(): print(f'MISSING {rel}'); ok=False; continue
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    match=digest==meta['sha256']; print(('OK ' if match else 'FAIL ')+rel+' '+digest)
    ok=ok and match
raise SystemExit(0 if ok else 2)
