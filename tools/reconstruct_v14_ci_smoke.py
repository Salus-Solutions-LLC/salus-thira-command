#!/usr/bin/env python3
import base64, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ARCH=ROOT/'source_archives'/'v1.4'
parts=sorted(ARCH.glob('ci_smoke.b64.part*'))
if not parts: raise SystemExit('Missing v1.4 CI smoke chunks')
out=base64.b64decode(''.join(p.read_text(encoding='ascii') for p in parts),validate=True)
expected='51e6840df4fc30fb1e871281d71b433ac697a313d0cf88a28655bca4bff7fcfc'
if hashlib.sha256(out).hexdigest()!=expected: raise SystemExit('v1.4 CI smoke SHA-256 mismatch')
path=ROOT/'tools'/'ci_v14_smoke.py'; path.write_bytes(out)
print(f'reconstructed {path.relative_to(ROOT)} {expected}')
