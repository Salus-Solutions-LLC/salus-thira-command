#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; m=json.loads((ROOT/'source_archives'/'security-codeql-v14'/'manifest.json').read_text())
for rel,meta in m['files'].items():
 p=ROOT/rel
 if not p.is_file() or p.stat().st_size!=meta['target_size_bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=meta['target_sha256']: raise SystemExit(f'Security source verification failed: {rel}')
print('SECURITY_SOURCE_VERIFICATION_PASS')
