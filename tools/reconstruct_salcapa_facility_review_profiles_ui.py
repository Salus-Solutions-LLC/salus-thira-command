#!/usr/bin/env python3
"""Reconstruct the governed facility review-profile interface sources."""

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = (
    (
        ROOT / "source_archives/development/salcapa-facility-review-profiles.js.source",
        ROOT / "static/salcapa-facility-review-profiles.js",
        "0dc145e2d585fa9805df0d6a78edd58c08b292a441196c627a9797f4cb7c4a15",
        8517,
    ),
    (
        ROOT / "source_archives/development/ci_salcapa_facility_review_profiles_ui_smoke.py.source",
        ROOT / "tools/ci_salcapa_facility_review_profiles_ui_smoke.py",
        "0de0adf53366cbf83b4a1146e254efc27f8f93c83fe35f4ef1e963f7f0748bf5",
        2835,
    ),
)

for archive, target, target_sha, target_size in ARTIFACTS:
    content = archive.read_bytes()
    if len(content) != target_size or hashlib.sha256(content).hexdigest() != target_sha:
        raise SystemExit(f"Invalid reconstructed source: {target.name}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
print("SALCAPA_FACILITY_REVIEW_PROFILES_UI_RECONSTRUCTION_PASS")
