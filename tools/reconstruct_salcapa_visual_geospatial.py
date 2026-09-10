#!/usr/bin/env python3
"""Reconstruct reviewed Issue #236 visual and geospatial sources."""

import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_visual_geospatial.py.gz",
        ROOT / "salcapa_visual_geospatial.py",
        "f4f3ec4f67ef8397a0ba1dbcaa31f5134a192f4acc74f4f6ce4267221ea792b8",
        "dae5416d401403b4f77bf4428428b811205a04bbbc8ac34b6691f5b866048a71",
        44110,
    ),
    (
        ROOT / "source_archives/development/salcapa_visual_geospatial_worker.py.gz",
        ROOT / "tools/salcapa_visual_geospatial_worker.py",
        "5d303f50e379830d039a08ca5055bd57ca61db0351e462f54ab79ec2777724bf",
        "862e80fc08ed5b8e4cd170d2f4a2aa4e34eb324f02855bfcc255d6bc8465c715",
        13956,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_visual_geospatial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_visual_geospatial_smoke.py",
        "779fc2565d30711d7d010afcb3ff31e5558672ba4a81f89b9c0fa104695096fb",
        "df93c8c204bea7385a0fd545a3abbb7de1c7b19318cfd8a7ac53cde7c34bf938",
        12016,
    ),
    (
        ROOT / "source_archives/development/salcapa-visual-geospatial.js.gz",
        ROOT / "static/salcapa-visual-geospatial.js",
        "4804d8e0125c3d6e2311da615caa3ddc7c964916b2e8ed52c33891d22623fe84",
        "1cb2f024b4f7b9f7b9bf0438e4c2a956445693dbb96f5b8ea16b9967664bb051",
        10463,
    ),
    (
        ROOT / "source_archives/development/salcapa-visual-geospatial.css.gz",
        ROOT / "static/salcapa-visual-geospatial.css",
        "4a478e0c7712e1cbb3a68658bff40f38fd53c451e04fd03d18a2593c16a58ed7",
        "529a793278ef4d23adfe00611bb7b61e04a638b993a90aeb2f88bb81b1bfcc16",
        574,
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
print("SALCAPA_VISUAL_GEOSPATIAL_RECONSTRUCTION_PASS")
