#!/usr/bin/env python3
"""Reconstruct reviewed Issue #133 contextual-intake sources."""
import gzip
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa_contextual_intake.py.gz",
        ROOT / "salcapa_contextual_intake.py",
        "7c2eeae7a079956dec4fd2a530dde7b65a6764ed3604d862606bfe5ed5c020f0",
        "48d9abf9efc51ad7761b800cb5bc8ff2890fd5ced43e36800447e4d58c678e15",
        7625,
    ),
    (
        ROOT / "source_archives/development/salcapa-contextual-intake.js.gz",
        ROOT / "static/salcapa-contextual-intake.js",
        "39d8b7b7c1f43ca0a4bd6e9a2e2f8a7f4d0c58b943f311c9c7e4d308db6ac521",
        "41296c97197029d2b5033b954823890deeea5e83badde41050a84995cf89cdb4",
        7969,
    ),
    (
        ROOT / "source_archives/development/salcapa-contextual-intake.css.gz",
        ROOT / "static/salcapa-contextual-intake.css",
        "528cb903cbfc9bc4c07300755f4a938eaac5cadc622f9568d2a2d1f46e304bda",
        "5e4bfa079dd2e4313feaeee90a33eaadd692dfe46b79f35b8a6ca560c7b6da1e",
        595,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_contextual_intake_smoke.py.gz",
        ROOT / "tools/ci_salcapa_contextual_intake_smoke.py",
        "b8f251a9362c0fbfe57ccedd91819dd03cccbf1bb5dad73df1e63fe4e0d0b2da",
        "377218a5aef188620ed982a0c12dfee97051cac98bfc62a4c7df3f45d8e9672a",
        6375,
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
print("SALCAPA_CONTEXTUAL_INTAKE_RECONSTRUCTION_PASS")
