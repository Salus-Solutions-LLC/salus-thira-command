#!/usr/bin/env python3
"""Reconstruct reviewed demonstration-evaluator sources."""

import base64
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_demo_evaluator.py.gz.b64", "salcapa_demo_evaluator.py", "b557f3210fc82787806b7e417d796236ce699272f526655abd9b75f8f2c1ca7b", "499f50c40b5bfc717bd23acb8a1b65dadffc18c51bebfd8d37d34003db1ac777", "2d2c7c17e7ca5da455f1d15b5bde19d94140907313ff4a6c5eac7d340a796f2c", 6929),
    ("demo-environments.js.gz.b64", "static/demo-environments.js", "7db43f9ddee964d7582e928d0f1ce980f6ad9380f428ac452c992f8c02894281", "bd6f678c59803ae6f959f0bddfa9b3b910eed5cf4782587e0b5dfad4e9c3c559", "b3bef2e07cb6eec070848eeeb53b1bbfcd071d230f26bd1d89d0f606338af6ed", 4614),
    ("ci_salcapa_demo_evaluator_smoke.py.gz.b64", "tools/ci_salcapa_demo_evaluator_smoke.py", "ba5cc3d3ea28f053353a56f33f488f241a76b851d89f827f685f9de4dcf9d37a", "8484ef71382981cd5e51f471c31f9f1172112080b78325cc7e94aa7d570e5b13", "e2c91011f549cc85e7b981a0191dd5ec83a0dda9834941df1d6a345126c2f2d0", 5597),
)

for archive_name, target_name, encoded_sha, archive_sha, target_sha, target_size in ARTIFACTS:
    encoded = (ROOT / "source_archives/development" / archive_name).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != encoded_sha:
        raise SystemExit(f"Invalid encoded source artifact digest: {archive_name}")
    compressed = base64.b64decode(encoded, validate=False)
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive_name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target_name}")
    target = ROOT / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

print("SALCAPA_DEMO_EVALUATOR_RECONSTRUCTION_PASS")
