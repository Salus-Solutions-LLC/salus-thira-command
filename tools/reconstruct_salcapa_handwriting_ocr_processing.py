#!/usr/bin/env python3
"""Reconstruct reviewed v3.109 handwriting and difficult-text recognition sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    ("salcapa_handwriting_ocr_processing.py.gz", "salcapa_handwriting_ocr_processing.py", "a0d3cbbf3ed32c0508c6dbdd10611ee8dd661e7d36e1ad8ac8d270407780c258", "71c8db56597005287a7cc171bdfadcbac7fb722cc60d148856e50eb08bd5b3ac", 33712),
    ("salcapa_handwriting_ocr_worker.py.gz", "tools/salcapa_handwriting_ocr_worker.py", "f14f6292ccdf304f38c4164e49accdd85f3c92dbcaeda714c93e77f2b0c99d96", "93ef4891c3a08d1fdf00ee44e8b7ea13340f7b211df5360ae7b6cc906917ae43", 9365),
    ("ci_salcapa_handwriting_ocr_processing_smoke.py.gz", "tools/ci_salcapa_handwriting_ocr_processing_smoke.py", "ba99631e2adffd5b602b28b347268412344b78c4dc97d03d7cbc878cc7ff4d01", "69cc1880443ddf9772769af12b9fb54c2c0ea099d46d1c2672266e231d1987c0", 9227),
    ("salcapa-handwriting-ocr.js.gz", "static/salcapa-handwriting-ocr.js", "32058912bad07caa5d24b21db65cf63b6598a83494e0ca4a44301e75cd564bd1", "34a5da49ccd3d5f8b56acc42556d012718bc423e39830013f92f31cc1f927cf5", 7340),
)

for archive_name, target_name, archive_sha, target_sha, target_size in ARTIFACTS:
    compressed = (ROOT / "source_archives/development" / archive_name).read_bytes()
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive_name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target_name}")
    target = ROOT / target_name; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(content)

print("SALCAPA_HANDWRITING_OCR_PROCESSING_RECONSTRUCTION_PASS")
