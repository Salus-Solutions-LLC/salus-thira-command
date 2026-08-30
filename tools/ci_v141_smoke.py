#!/usr/bin/env python3
"""Deterministic launcher for the archived v1.4.1 lifecycle and security patch smoke."""
import base64,gzip
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; PAYLOAD=ROOT/'source_archives'/'v1.4.1'/'ci_v141_smoke.py.gz.b64'
raw=gzip.decompress(base64.b64decode(PAYLOAD.read_text(),validate=True)); exec(compile(raw,str(PAYLOAD)+'::ci_v141_smoke.py','exec'),{'__name__':'__main__','__file__':str(ROOT/'tools'/'ci_v141_smoke.py')})
