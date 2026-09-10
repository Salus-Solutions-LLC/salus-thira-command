#!/usr/bin/env python3
"""Reconstruct reviewed v3.108 visual object-processing sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_visual_object_processing.py.gz", "salcapa_visual_object_processing.py", "f03af6d9db10a70a90ef44aadb91d4b46ece67f0a58f0c691d3814881f0bde72", "819503a5bd73d5eed9ba8370a7a00fe3dc3b26bcc331c110fc3919ebf7dfec5b", 26988),
    ("salcapa_visual_object_worker.py.gz", "tools/salcapa_visual_object_worker.py", "e868b842967bfad380e392b7c892ed82ae3cf8bc95d589e80a072c2454e3fe39", "93c746ccb839b7c10a53d59d84b999b2cd3fe0a5d517d3b3e09c3ad2713ba943", 7282),
    ("ci_salcapa_visual_object_processing_smoke.py.gz", "tools/ci_salcapa_visual_object_processing_smoke.py", "9f61fafe7ee45d548e3be4708d60d33f44306ee5e29277d7ba47b5e5c870bc02", "46232f35e5858b8aa5e04761713705de5749f89544f24d8014a9c78d97e0bdb1", 7962),
    ("salcapa-visual-object-ui.js.gz", "static/salcapa-visual-geospatial.js", "451ca84d65963aaeb12ade8f256f554b7058e1a423a424cf355b0c483eac9bee", "1f63fc2cd0eee4668165e1c9ceb7070835efd00a77018763b9f5af0f5e7688ad", 14932),
)

for archive_name, target_name, archive_sha, target_sha, target_size in ARTIFACTS:
    compressed = (ROOT / "source_archives/development" / archive_name).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive_name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target_name}")
    target = ROOT / target_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)

print("SALCAPA_VISUAL_OBJECT_PROCESSING_RECONSTRUCTION_PASS")
