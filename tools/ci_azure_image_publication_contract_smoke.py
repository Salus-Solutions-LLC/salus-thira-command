#!/usr/bin/env python3
"""Verify the immutable-image publication workflow remains activation-led and fail-closed."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "azure-image-publish.yml"
ACTIVATION = ROOT / "deploy" / "azure" / "activations" / "image-dev.json"


def require(fragment: str, text: str) -> None:
    if fragment not in text:
        raise AssertionError(f"Missing required publication control: {fragment}")


workflow = WORKFLOW.read_text(encoding="utf-8")
activation = json.loads(ACTIVATION.read_text(encoding="utf-8"))

# Updating the workflow cannot publish an image: only the separately governed
# activation record is in the publication workflow's push path filter.
trigger_prefix = workflow.split("permissions:", 1)[0]
require("- 'deploy/azure/activations/image-dev.json'", trigger_prefix)
assert "azure-image-publish.yml" not in trigger_prefix
assert "pull_request:" not in trigger_prefix
assert "workflow_dispatch:" not in trigger_prefix

# This candidate activation binds publication to exact frozen v3.112. A pull
# request cannot execute the push-only publication workflow; only the validated
# commit later advancing to the governed development branch can request it.
assert activation == {
    "schema_version": 1,
    "operation": "publish_image",
    "target_environment": "dev",
    "repository": "salcapa",
    "location": "southcentralus",
    "unique_suffix": "b48224",
    "approval_record": "MD-APPROVAL-AZURE-LEAN-20260904",
    "source_release": "release/v3.112",
    "source_commit": "1d1759375d37b7de884331c06833de8c727ac5af",
    "activation_key": "salcapa-v3.112-image-1d175937",
}

# Publication is release-driven and must bind a release branch, exact commit,
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
