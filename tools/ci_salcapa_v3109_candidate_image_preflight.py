#!/usr/bin/env python3
"""Verify the exact v3.109 reference-image boundary without authorizing deployment."""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parents[1]
FROZEN_ROOT = pathlib.Path(os.environ.get("SALCAPA_FROZEN_V3109_ROOT", ROOT / "frozen-v3109"))
CONTRACT = ROOT / "deploy" / "azure" / "candidates" / "v3.109-reference-image-preflight.json"
ACCEPTED_IMAGE = ROOT / "deploy" / "azure" / "activations" / "image-dev.json"
ACCEPTED_APPLICATION = ROOT / "deploy" / "azure" / "activations" / "application-dev.json"
CONTINUITY = ROOT / "docs" / "demo-deployment-continuity.md"

V3109_COMMIT = "361a38300faddd7e9a93153c0629739acef870a0"
V336_COMMIT = "63d513605f908d3308bb5dd1bbdbf1061878452b"
V336_DIGEST = "sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46"
PINNED_BLOBS = {
    "Dockerfile": "15468459038f2ba6786d4e7693a76fda758c3c7d",
    "salcapa_runtime.py": "9f568d750613adaeebdfa22575c533586c8e3b53",
    "requirements.txt": "f5c385199b1d15e86bbdfde866a2f5d9816bc887",
}


def load_json(path: pathlib.Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def front_matter(path: pathlib.Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, raw, _ = text.split("---", 2)
    return {
        key.strip(): value.strip()
        for line in raw.strip().splitlines()
        for key, separator, value in [line.partition(":")]
        if separator
    }


def git_output(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(FROZEN_ROOT), *args],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


contract = load_json(CONTRACT)
assert contract == {
    "schema_version": 1,
    "operation": "preflight_reference_image",
    "target_environment": "dev",
    "source_release": "release/v3.109",
    "source_commit": V3109_COMMIT,
    "dockerfile_blob": PINNED_BLOBS["Dockerfile"],
    "runtime_blob": PINNED_BLOBS["salcapa_runtime.py"],
    "requirements_blob": PINNED_BLOBS["requirements.txt"],
    "accepted_deployed_release": "v3.36",
    "accepted_deployed_commit": V336_COMMIT,
    "accepted_image_digest": V336_DIGEST,
    "fixture_capability_included": False,
    "publish_authorized": False,
    "deploy_authorized": False,
    "traffic_change_authorized": False,
    "cost_change_authorized": False,
    "purpose": "Verify exact frozen v3.109 image lineage and runtime packaging without contacting or changing Azure.",
    "next_gate": "Freeze a successor release containing the verified Issue #124 fixture and preflight capabilities before publication or deployment.",
}

assert FROZEN_ROOT.is_dir(), "exact frozen v3.109 checkout is required"
assert git_output("rev-parse", "HEAD") == V3109_COMMIT
assert git_output("status", "--porcelain") == ""
for path, expected_blob in PINNED_BLOBS.items():
    assert git_output("hash-object", path) == expected_blob, path

runtime = (FROZEN_ROOT / "salcapa_runtime.py").read_text(encoding="utf-8")
assert 'SALCAPA_RELEASE_VERSION = "3.109"' in runtime
assert not (FROZEN_ROOT / "salcapa_demo_fixtures.py").exists()
assert not (FROZEN_ROOT / "tools" / "reconstruct_salcapa_demo_fixtures.py").exists()

accepted_image = load_json(ACCEPTED_IMAGE)
accepted_application = load_json(ACCEPTED_APPLICATION)
assert accepted_image["source_release"] == "release/v3.36"
assert accepted_image["source_commit"] == V336_COMMIT
assert accepted_application["source_release"] == "release/v3.36"
assert accepted_application["source_commit"] == V336_COMMIT
assert accepted_application["image_digest"].endswith(V336_DIGEST)

continuity = front_matter(CONTINUITY)
assert continuity["deployed_release"] == "v3.36"
assert continuity["deployed_commit"] == V336_COMMIT
assert continuity["image_digest"] == V336_DIGEST
assert continuity["current_stable_release"] == "v3.109"
assert continuity["current_stable_commit"] == V3109_COMMIT
assert continuity["promotion_readiness"] == "not_ready"
assert continuity["genuine_blocker"] != "none"

for forbidden in ("password", "client_secret", "access_token", "connection_string"):
    assert not re.search(rf'(?i)"{forbidden}"\s*:', CONTRACT.read_text(encoding="utf-8"))

print(
    "Exact frozen v3.109 reference-image lineage passed; publication, deployment, "
    "traffic, and cost changes remain unauthorized."
)
