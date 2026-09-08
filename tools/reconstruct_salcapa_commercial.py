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
        "15fa40818c3c0122358aacc3c323729a5bf95cc282cd8f29d6e6b4b22bf48fbf",
        "73b19b78dd799a14420d3fb4fc8c2ff76eb464599de0490d5d556fbdf19da069",
        98948,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_commercial_smoke.py.gz",
        ROOT / "tools/ci_salcapa_commercial_smoke.py",
        "4ff005519c8ddf9eaab0191d3b20a1dcc7bff3a41183f08c85b048b94b1d22f9",
        "4381321eb40be403ba5f6d731a83df5e8dd129a0749ef3ef36e7a8fe8fa0d277",
        30965,
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
