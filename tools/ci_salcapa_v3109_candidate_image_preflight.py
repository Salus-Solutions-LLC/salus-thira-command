#!/usr/bin/env python3
"""Verify the exact v3.109 reference-image boundary without blocking newer governed releases."""

from __future__ import annotations

import json
import os
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
FROZEN_ROOT = pathlib.Path(os.environ.get("SALCAPA_FROZEN_V3109_ROOT", ROOT / "frozen-v3109"))
CONTRACT = ROOT / "deploy" / "azure" / "candidates" / "v3.109-reference-image-preflight.json"
IMAGE_PUBLICATION = ROOT / "deploy" / "azure" / "activations" / "image-dev.json"
ACCEPTED_APPLICATION = ROOT / "deploy" / "azure" / "activations" / "application-dev.json"
CONTINUITY = ROOT / "docs" / "demo-deployment-continuity.md"
BUILD_CONTINUITY = ROOT / "docs" / "build-continuity.md"

V3109_COMMIT = "361a38300faddd7e9a93153c0629739acef870a0"
V336_COMMIT = "63d513605f908d3308bb5dd1bbdbf1061878452b"
V336_DIGEST = "sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46"
V3111_COMMIT = "8bf4614ec79a27641c40dc1a21e1790746a08604"
V3111_DIGEST = "sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311"
V3112_COMMIT = "1d1759375d37b7de884331c06833de8c727ac5af"
V3112_DIGEST = "sha256:605822c4f48a82ac9823a2f80e846c0cc6b9ac944afe20c95240cae854e549ce"
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

# The historical v3.109 reference remains immutable, while the current image
# activation may legitimately advance to the currently frozen SalCAPA release.
image_publication = load_json(IMAGE_PUBLICATION)
accepted_application = load_json(ACCEPTED_APPLICATION)
build_continuity = front_matter(BUILD_CONTINUITY)
current_frozen_release = build_continuity["current_frozen_release"]
current_frozen_commit = build_continuity["current_frozen_commit"]
assert image_publication["source_release"] == f"release/{current_frozen_release}"
assert image_publication["source_commit"] == current_frozen_commit
assert image_publication["activation_key"] == (
    f"salcapa-{current_frozen_release}-image-{current_frozen_commit[:8]}"
)

# The accepted live application remains the rollback truth until a newer image
# is published and separately promoted through the governed application gate.
assert accepted_application["source_release"] == "release/v3.112"
assert accepted_application["source_commit"] == V3112_COMMIT
assert accepted_application["image_digest"].endswith(V3112_DIGEST)
assert accepted_application["rollback_release"] == "release/v3.111"
assert accepted_application["rollback_commit"] == V3111_COMMIT
assert accepted_application["rollback_image_digest"].endswith(V3111_DIGEST)

continuity = front_matter(CONTINUITY)
assert continuity["current_stable_release"] == "v3.112"
assert continuity["current_stable_commit"] == V3112_COMMIT
if continuity["promotion_readiness"] == "accepted":
    assert continuity["deployed_release"] == "v3.112"
    assert continuity["deployed_commit"] == V3112_COMMIT
    assert continuity["image_digest"] == V3112_DIGEST
    assert continuity["promotion_candidate_image_acceptance"] == "immutable_image_deployed_and_accepted"
    assert continuity["fictional_member_seed_state"] == "verified"
    assert continuity["critical_journey_acceptance"] == "verified"
    assert continuity["genuine_blocker"] == "none"
else:
    assert continuity["promotion_readiness"] in {"preflight_ready", "deployed_awaiting_live_acceptance"}
    assert continuity["deployed_release"] in {"v3.111", "v3.112"}
    if continuity["deployed_release"] == "v3.111":
        assert continuity["deployed_commit"] == V3111_COMMIT
        assert continuity["image_digest"] == V3111_DIGEST
    else:
        assert continuity["deployed_commit"] == V3112_COMMIT
        assert continuity["image_digest"] == V3112_DIGEST
    assert continuity["genuine_blocker"] != "none"

for forbidden in ("password", "client_secret", "access_token", "connection_string"):
    assert not re.search(rf'(?i)"{forbidden}"\s*:', CONTRACT.read_text(encoding="utf-8"))

print(
    "Exact frozen v3.109 reference-image lineage passed; newer image publication "
    "is bound to the currently frozen governed release without altering historical evidence."
)
