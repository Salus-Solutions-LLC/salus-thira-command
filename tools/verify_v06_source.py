#!/usr/bin/env python3
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'source_archives'/'v0.6'/'manifest.json').read_text())
failed=False
for target,meta in manifest.items():
    path=ROOT/target
    digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'MISSING'
    ok=digest==meta['sha256']; print(('OK' if ok else 'FAIL'),target,digest)
    failed|=not ok
raise SystemExit(1 if failed else 0)
