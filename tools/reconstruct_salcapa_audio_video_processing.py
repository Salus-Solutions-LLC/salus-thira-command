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
        "104cef025da77b8fe033d4c4d36d311474730f8b5936cd399e81f446ce46c078",
        "89c10371a66fe75b81cac01a328db0ef3ae7af83410949d6d1d2545793b888f3",
        15822,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_audio_video_processing_smoke.py.gz",
        ROOT / "tools/ci_salcapa_audio_video_processing_smoke.py",
        "55adbe8e7f3b8cc37d894283a2b3f2e05f8248fe9b26119b4b3ef95d057707c2",
        "9f795846a7ed23d914bbba844b7d9fdb31153f14dda303d39d9c3b51e1a40045",
        5367,
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
