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
        "26ae648fd3db9825fd1b9fa08e634f31e6cc372ffc1a6070eb0e8d7adde73a60",
        "b457d29d48ec3fe60b312239523cc427038d0088bae7bf5cca6e44ad613c8b54",
        15976,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_audio_video_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_audio_video_processing_smoke.py",
        "f0929ff539ed13746deafd3252279cf80eefdba912b4daed1cca25806b8494e0",
        "00da5f9f83324d56ed4f928c50fd57ce1ebb5ccd9d66ef5cf1bdee3888a71b87",
        6357,
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
