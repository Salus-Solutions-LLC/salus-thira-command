#!/usr/bin/env python3
"""Reconstruct reviewed demonstration-evaluator sources."""

import base64
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_demo_evaluator.py.gz.b64", "salcapa_demo_evaluator.py", "1277d883991671b62f6f2f8ed2796ed7e397ae682ab232a2319153aaa70f1079", "5050b8c52bc7b96007dd3ec26d136a5846c4f03d718c2432f2d6baf383b9d997", "6bcd3ba106b00883b97d0db23e982e61cfb03f4995f104440e17533f4b481e82", 6989),
    ("demo-environments.js.gz.b64", "static/demo-environments.js", "7db43f9ddee964d7582e928d0f1ce980f6ad9380f428ac452c992f8c02894281", "bd6f678c59803ae6f959f0bddfa9b3b910eed5cf4782587e0b5dfad4e9c3c559", "b3bef2e07cb6eec070848eeeb53b1bbfcd071d230f26bd1d89d0f606338af6ed", 4614),
    ("ci_salcapa_demo_evaluator_smoke.py.gz.b64", "tools/ci_salcapa_demo_evaluator_smoke.py", "4530646a8cee7e5188a935de2de74f33c2480ab578305c9eab3645d05c296806", "04bc4995ed6c8b7304eedac0d8c31c99a3e1e3c961a7ef642a996755fbee8c08", "804d052ef91f2c848806bcde1c73256dd40abd311eb65dda0009f23a59e9e413", 5216),
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
