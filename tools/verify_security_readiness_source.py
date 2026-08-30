#!/usr/bin/env python3
import hashlib,json
from pathlib import Path
R=Path(__file__).resolve().parents[1];m=json.loads((R/'source_archives'/'security-codeql-readiness'/'manifest.json').read_text());p=R/'app.py';x=m['files']['app.py']
if not p.is_file() or p.stat().st_size!=x['target_size_bytes'] or hashlib.sha256(p.read_bytes()).hexdigest()!=x['target_sha256']: raise SystemExit('Readiness source verification failed')
print('READINESS_SOURCE_VERIFICATION_PASS')
