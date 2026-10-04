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
V3113_COMMIT = "9d9873203fffd8c8ae477123ea94eb35b27c2acd"
V3113_DIGEST = "sha256:84fe4ca875ec1d8478aa617fcd873adcf62c5eba78134ea4575de8471bfd9eb8"
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

# The historical v3.109 reference remains immutable. Current activation
# records are validated by their own governed lineage rather than a stale
# continuity checkpoint so later releases do not break this historical gate.
image_publication = load_json(IMAGE_PUBLICATION)
accepted_application = load_json(ACCEPTED_APPLICATION)
sha_pattern = re.compile(r"^[0-9a-f]{40}$")
release_pattern = re.compile(r"^release/v[0-9]+[.][0-9]+$")
digest_pattern = re.compile(
    r"^salcapadevb48224acr[.]azurecr[.]io/salcapa@sha256:[0-9a-f]{64}$"
)

assert image_publication["operation"] == "publish_image"
assert image_publication["target_environment"] == "dev"
assert release_pattern.fullmatch(str(image_publication["source_release"]))
assert sha_pattern.fullmatch(str(image_publication["source_commit"]))
image_release = str(image_publication["source_release"]).removeprefix("release/")
assert image_publication["activation_key"] == (
    f"salcapa-{image_release}-image-{str(image_publication['source_commit'])[:8]}"
)

# Image publication intentionally precedes application promotion. The pending
# image must be the immediate successor to the currently accepted application;
# the accepted application remains unchanged until the digest is known and a
# separate deployment activation is validated.
assert accepted_application["operation"] == "deploy_application"
assert accepted_application["target_environment"] == "dev"
assert release_pattern.fullmatch(str(accepted_application["source_release"]))
assert sha_pattern.fullmatch(str(accepted_application["source_commit"]))
assert digest_pattern.fullmatch(str(accepted_application["image_digest"]))

def release_number(value: object) -> tuple[int, int]:
    match = re.fullmatch(r"release/v(?P<major>[0-9]+)[.](?P<minor>[0-9]+)", str(value))
    assert match is not None
    return int(match.group("major")), int(match.group("minor"))

published_version = release_number(image_publication["source_release"])
accepted_version = release_number(accepted_application["source_release"])
if published_version == accepted_version:
    # Deployment-ready: the application activation is bound to the published
    # frozen source and will additionally bind the exact immutable digest.
    assert image_publication["source_commit"] == accepted_application["source_commit"]
else:
    # Publication-staged: ordinarily the next image is the immediate successor.
    # A bounded release gap is allowed only for an exact recorded repair lineage;
    # no generic version skip can qualify an image for publication.
    immediate_successor = (accepted_version[0], accepted_version[1] + 1)
    superseding_successor = (accepted_version[0], accepted_version[1] + 2)
    if (accepted_version, published_version) == ((3, 210), (3, 214)):
        # v3.213 is the running scanner worker, but its fictional Clean event
        # stayed Pending. The reviewed null-details repair is frozen in v3.214;
        # neither v3.211-3.213 became the accepted Member application.
        continuity = (ROOT / "docs" / "build-continuity.md").read_text(encoding="utf-8")
        assert "current_frozen_release: v3.214" in continuity
        assert "current_frozen_commit: 04b6e6ae47e83dcab9d5c76edb56f95327f1a7fc" in continuity
        assert "candidate_release: v3.214" in continuity
        assert "v3211_superseded_before_publication" in continuity
        assert "v3212_private_scanner_acceptance_failed" in continuity
        assert "v3213_scanner_clean_event_shape_failed" in continuity
        assert image_publication["source_commit"] == "04b6e6ae47e83dcab9d5c76edb56f95327f1a7fc"
    elif (accepted_version, published_version) == ((3, 210), (3, 213)):
        # v3.211 was superseded before publication. The v3.212 image was
        # published only for private scanner acceptance; that test failed and
        # neither release became the accepted Member application. Require the
        # exact recorded repair lineage before allowing this bounded skip.
        continuity = (ROOT / "docs" / "build-continuity.md").read_text(encoding="utf-8")
        assert "current_frozen_release: v3.213" in continuity
        assert "current_frozen_commit: 7ec414abe94092e631f0a4b7222fd99ce34b7e26" in continuity
        assert "candidate_release: v3.213" in continuity
        assert "v3211_superseded_before_publication" in continuity
        assert "v3212_private_scanner_acceptance_failed" in continuity
        assert image_publication["source_commit"] == "7ec414abe94092e631f0a4b7222fd99ce34b7e26"
    elif published_version == superseding_successor:
        continuity = (ROOT / "docs" / "build-continuity.md").read_text(encoding="utf-8")
        skipped = f"v{immediate_successor[0]}.{immediate_successor[1]}"
        published = f"v{published_version[0]}.{published_version[1]}"
        # The skipped branch was frozen, but the accepted runtime can remain
        # two versions behind while a blocking repair supersedes that branch.
        if skipped == "v3.177":
            assert "current_frozen_release: v3.176" in continuity
            assert "v3.177_abandoned_before_publication" in continuity
        else:
            assert f"current_frozen_release: {skipped}" in continuity
        assert f"candidate_release: {published}" in continuity
        assert f"{skipped.replace('.', '')}_superseded_before_publication" in continuity
    else:
        assert published_version == immediate_successor
    assert image_publication["source_commit"] != accepted_application["source_commit"]

# The current accepted activation must itself retain a distinct, structurally
# valid rollback release while the successor image is being published.
assert release_pattern.fullmatch(str(accepted_application["rollback_release"]))
assert sha_pattern.fullmatch(str(accepted_application["rollback_commit"]))
assert digest_pattern.fullmatch(str(accepted_application["rollback_image_digest"]))
assert accepted_application["rollback_release"] != accepted_application["source_release"]
assert accepted_application["rollback_commit"] != accepted_application["source_commit"]
assert accepted_application["rollback_image_digest"] != accepted_application["image_digest"]

for forbidden in ("password", "client_secret", "access_token", "connection_string"):
    assert not re.search(rf'(?i)"{forbidden}"\s*:', CONTRACT.read_text(encoding="utf-8"))

print(
    "Exact frozen v3.109 reference-image lineage passed; newer image publication "
    "is bound to the currently frozen governed release without altering historical evidence."
)
