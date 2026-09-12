#!/usr/bin/env python3
"""Reconstruct reviewed demonstration-evaluator sources."""

import base64
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_demo_evaluator.py.gz.b64", "salcapa_demo_evaluator.py", "dad134aea53f4e4be2d46e536f3144fdfb9ed6a6d2ed703599cd552618be51e2", "eeef2e917138cb805988e5cddb49398b5e226b1941652ab6b4b1ab3717c431ad", "306372859311b95861abc804a532337db8d8af49223141914cd6435999a60e09", 6982),
    ("demo-environments.js.gz.b64", "static/demo-environments.js", "4b6ae8f49a4b5b5599197ae21d0840560d504267b3eecedee264af497ec91890", "a6ef6e271ad74b657096500f814d262b640ba0c86140122fa9d6377b427d9096", "cc154edb48d800e925f13925ac8bd62d692a7cf9f3b8631079e5f7b8395a05de", 4395),
    ("ci_salcapa_demo_evaluator_smoke.py.gz.b64", "tools/ci_salcapa_demo_evaluator_smoke.py", "f67285a0dfa76047e2884deff88f026cf44db6dfeb19813bb2f9163b387a98ce", "ea2b4a237517b9f26a21307c69d97f2184a1ee0b8e83d9a104ef8e869406a901", "624daa0230aae9f005adf27bc7179b6f63c02038fb4e7633317b95f40502f19d", 5236),
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
