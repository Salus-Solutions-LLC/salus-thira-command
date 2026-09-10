#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 image-metadata and OCR processing sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_image_ocr_processing.py.gz",
        ROOT / "salcapa_image_ocr_processing.py",
        "3e5afe86249155737f04774a9c3a87fb10e1920378a1401f82b6c88b8fb0ad03",
        "edebf2fb62f8698966ee067f7cb6d0314f5bd6f4cc0a1364be1b0a1bd40d5ded",
        7133,
    ),
    (
        ROOT / "source_archives/development/salcapa_image_ocr_worker.py.gz",
        ROOT / "tools/salcapa_image_ocr_worker.py",
        "77da533b4bb5b29440ce56e93b71df93ea429b11a78318321bc66313dbed9e50",
        "c0a4d481d207ca505d098fb1ccadaa07e70d7242658228c76a32db20dca656b4",
        12023,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_image_ocr_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_image_ocr_processing_smoke.py",
        "1afaf732189bed4ce70f951806762d13a4b4a319a61b2d3cc69ccc154d681a7a",
        "0c5fb24376ff80848568452e672939ab7c126b256f25a3ef716eb999428782be",
        4760,
    ),
)

for archive, target, archive_sha, target_sha, target_size in ARTIFACTS:
    compressed = archive.read_bytes()
    if hashlib.sha256(compressed).hexdigest() != archive_sha:
        raise SystemExit(f"Invalid source artifact digest: {archive.name}")
    content = gzip.decompress(compressed)
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
print("SALCAPA_IMAGE_OCR_PROCESSING_RECONSTRUCTION_PASS")
