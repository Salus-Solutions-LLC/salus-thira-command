#!/usr/bin/env python3
from pathlib import Path
import hashlib
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    ROOT / 'app.py': '5572cf66373ecf906a1565a6f8d1e10cf3a294e24dbb79550f2cefef86fe06cf',
    ROOT / 'static' / 'app.js': '1a6dafabb637dc477143c3666d519f4d9d7ebe844fca067ee2566af373f5af8c',
}

ok = True
for path, expected in EXPECTED.items():
    if not path.exists():
        print(f'MISSING {path.relative_to(ROOT)}')
        ok = False
        continue
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    status = 'OK' if actual == expected else 'MISMATCH'
    print(f'{status} {path.relative_to(ROOT)} {actual}')
    ok &= actual == expected
sys.exit(0 if ok else 1)
