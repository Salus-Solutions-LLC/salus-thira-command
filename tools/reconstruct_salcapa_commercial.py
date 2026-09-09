#!/usr/bin/env python3
"""Reconstruct reviewed Issue #154 commercial-planning sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_commercial.py.gz",
        ROOT / "salcapa_commercial.py",
        "6f7d37f13a32c921957cbbd394ab5489bf53b77e4c5328e669aed30055dc34f8",
        "38d03f977bef4a79ec382714d7694d78a7abf57e3fc4c98e34583ec1dbb45903",
        171252,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_commercial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_commercial_smoke.py",
        "af0ba851e4444a43c431c48ce194ad038a00ef20a8aa0692e93b69a5bd36a09c",
        "f0f7b8bac23675182dc92da31cad276b01ad2699e92c39f6d46646bdd749037a",
        50592,
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
print("SALCAPA_COMMERCIAL_RECONSTRUCTION_PASS")
