#!/usr/bin/env python3
"""Reconstruct reviewed SalINTEL governed handoff sources."""
import gzip
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (ROOT / "source_archives" / "development" / "salintel_handoffs.py.gz",
     ROOT / "salintel_handoffs.py",
     "137d85906d27494cd354b4a8402d293870c6024d70a908adc9d7f03f9fa04233",
     "f8e3a39600e9b79e8ef52d2cd268a50dcda766bf1710225afa31dcbd67414b95", 15230),
    (ROOT / "source_archives" / "development" / "ci_salintel_handoffs_smoke.py.gz",
     ROOT / "tools" / "ci_salintel_handoffs_smoke.py",
     "80660bf0498e59ee4489189663c23872dc03d293d86463cc2811c7b04ca8dc03",
     "aecf0f3a96ac71b8566bb1760f80982fd2f6a6bbb0b2f4fb31e1dc6e9f5e0371", 9822),
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
    print(f"reconstructed {target.relative_to(ROOT)} {target_sha}")
