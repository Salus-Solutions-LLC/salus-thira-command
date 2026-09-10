#!/usr/bin/env python3
"""Reconstruct reviewed Issue #131 audio/video transcription sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_audio_video_processing.py.gz",
        ROOT / "salcapa_audio_video_processing.py",
        "39e5792d9c8e896885875da8b14f4092917a0ad0555789b27baebad1327f17fa",
        "fc6313183fb2396820e11c4a53ce000e9224844f9f957da6902f5aa4ca20359f",
        8919,
    ),
    (
        ROOT / "source_archives/development/salcapa_audio_video_worker.py.gz",
        ROOT / "tools/salcapa_audio_video_worker.py",
        "48c9bafbb88f28e43ad10319c592b948d3fe1e04d5c9d818b84c99b24b1d41f0",
        "0e7f4e49b5c499e4d4d529f80d458b814a10cdb4940c8bfd6d57d564bdb83577",
        15969,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_audio_video_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_audio_video_processing_smoke.py",
        "a2b80b2dbab214f9435746e732ee0fec9cc1fffa7afdaa337c6f7f2fade149bd",
        "d0dbf7b37638953516292dd5b23180ebd6e59b05af8d633db33e1f2359b06c38",
        6673,
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
print("SALCAPA_AUDIO_VIDEO_PROCESSING_RECONSTRUCTION_PASS")
