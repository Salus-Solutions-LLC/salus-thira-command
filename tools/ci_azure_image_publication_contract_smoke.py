#!/usr/bin/env python3
"""Verify immutable-image publication remains activation-led, release-bound, and fail-closed."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "azure-image-publish.yml"
ACTIVATION = ROOT / "deploy" / "azure" / "activations" / "image-dev.json"


def require(fragment: str, text: str) -> None:
    if fragment not in text:
        raise AssertionError(f"Missing required publication control: {fragment}")


workflow = WORKFLOW.read_text(encoding="utf-8")
activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))

# Updating workflow code alone cannot publish an image. Publication is requested
# only by a separately governed activation record advancing on development.
trigger_prefix = workflow.split("permissions:", 1)[0]
require("- 'deploy/azure/activations/image-dev.json'", trigger_prefix)
assert "azure-image-publish.yml" not in trigger_prefix
assert "pull_request:" not in trigger_prefix
assert "workflow_dispatch:" not in trigger_prefix

expected_keys = {
    "schema_version",
    "operation",
    "target_environment",
    "repository",
    "location",
    "unique_suffix",
    "approval_record",
    "source_release",
    "source_commit",
    "activation_key",
}
assert set(activation) == expected_keys
assert activation["schema_version"] == 1
assert activation["operation"] == "publish_image"
assert activation["target_environment"] == "dev"
assert activation["repository"] == "salcapa"
assert activation["location"] == "southcentralus"
assert activation["unique_suffix"] == "b48224"
assert activation["approval_record"] == "MD-APPROVAL-AZURE-LEAN-20260904"
assert re.fullmatch(r"release/v3\.\d+", activation["source_release"])
assert re.fullmatch(r"[0-9a-f]{40}", activation["source_commit"])
expected_key = (
    f"salcapa-{activation['source_release'].removeprefix('release/')}-image-"
    f"{activation['source_commit'][:8]}"
)
assert activation["activation_key"] == expected_key

# Publication is release-driven and binds the release branch, exact commit,
# runtime version, and derived activation key before contacting Azure.
require("ref: ${{ steps.activation.outputs.source_release }}", workflow)
assert "ref: release/v3.36" not in workflow
require('test("^release/v3\\\\.[0-9]+$")', workflow)
require('test("^[0-9a-f]{40}$")', workflow)
require('EXPECTED_ACTIVATION_KEY="salcapa-${SOURCE_RELEASE#release/}-image-${SOURCE_COMMIT:0:8}"', workflow)
require('test "$(git -C frozen-release rev-parse HEAD)" = "$SOURCE_COMMIT"', workflow)
require("Frozen runtime release identity does not match activation", workflow)
require('org.opencontainers.image.revision=$SOURCE_COMMIT', workflow)
require('org.opencontainers.image.version=$RELEASE_VERSION', workflow)
require('test "$(docker run --rm "$IMAGE_REFERENCE" id -u)" = "10001"', workflow)

# Azure authority stays narrow and identity is workload-federated. Publication
# never changes the running application or creates a mutable latest reference.
require("environment: salcapa-dev-approval", workflow)
require("id-token: write", workflow)
require("azure/login@7ddb5af1ef8758cf1353cf3b42f940aee27ba21c", workflow)
require('test "$AZURE_RESOURCE_GROUP" = "rg-salcapa-dev"', workflow)
require('(.role == "AcrPush" or .role == "Owner")', workflow)
require("Mutable latest tag: not used", workflow)
require("Container App deployment: not performed", workflow)
assert "az containerapp" not in workflow
assert "salcapa:latest" not in workflow
assert "client-secret:" not in workflow

print("Azure immutable-image publication contract smoke checks passed")
