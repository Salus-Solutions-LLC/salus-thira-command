#!/usr/bin/env python3
"""Deterministic launcher for the archived v1.4 release lifecycle smoke."""
import base64
import gzip
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = ROOT / "source_archives" / "v1.4" / "ci_v14_smoke.py.gz.b64"
raw = gzip.decompress(base64.b64decode(PAYLOAD.read_text(encoding="ascii"), validate=True))
code = compile(raw, str(PAYLOAD) + "::ci_v14_smoke.py", "exec")
exec(code, {"__name__": "__main__", "__file__": str(ROOT / "tools" / "ci_v14_smoke.py")})
