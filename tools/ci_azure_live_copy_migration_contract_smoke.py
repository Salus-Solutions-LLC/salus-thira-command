#!/usr/bin/env python3
"""Fail-closed contract checks for the inert Azure live-copy acceptance path."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "azure-live-copy-migration-acceptance.yml"
BICEP = ROOT / "infra" / "azure" / "live-copy-migration-acceptance.bicep"
ACTIVATION = ROOT / "deploy" / "azure" / "activations" / "live-copy-migration-dev.json"


def require(value: str, content: str) -> None:
    if value not in content:
        raise SystemExit(f"Live-copy migration acceptance contract is missing: {value}")


workflow = WORKFLOW.read_text(encoding="utf-8")
bicep = BICEP.read_text(encoding="utf-8")

for value in (
    "deploy/azure/activations/live-copy-migration-dev.json",
    "environment: salcapa-dev-approval",
    "permissions: {}",
    "needs: authorize",
    "id-token: write",
    "ref: release/v3.110",
    "935f0b7bea72375adc936f7904f4f74c2eb99643",
    "63d513605f908d3308bb5dd1bbdbf1061878452b",
    "sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44",
    "sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46",
    "accept_live_copy_migration",
    "salcapa-dev-b48224-v310-copy",
    'JOB_NAME="salcapa-dev-b48224-v310-job"',
    "restore_lag_minutes == 15",
    "trap cleanup EXIT",
    "az postgres flexible-server restore",
    "az deployment group create",
    "LIVE_COPY_MIGRATION_ACCEPTED",
    "Source database and running application configuration: unchanged",
    "lastModifiedAt:.systemData.lastModifiedAt",
    "sort_by(.name)",
    "Password, client secret, application deployment, traffic shift, and DNS change: none",
):
    require(value, workflow)

for value in (
    "temporary-live-copy-migration-acceptance",
    "var jobName = '${stem}-v310-job'",
    "image: imageDigest",
    "runtimeIdentity.id",
    "SALUS_POSTGRES_HOST",
    "restoredPostgresHost",
    "SALUS_POSTGRES_AUTH",
    "managed_identity",
    "salcapa_demo_fixtures",
    "FICTIONAL DEMONSTRATION DATA ONLY",
    "SALUS_OIDC_AUTO_PROVISION",
    "SALUS_SEED_DEMO",
):
    require(value, bicep)

trigger_prefix = workflow.split("permissions:", 1)[0]
for prohibited in ("pull_request:", "workflow_dispatch:", "schedule:"):
    if prohibited in trigger_prefix:
        raise SystemExit(f"Live-copy acceptance may not expose {prohibited}")
for prohibited in (
    "AZURE_CLIENT_SECRET",
    "POSTGRES_PASSWORD",
    "SALUS_DATABASE_URL",
    "az containerapp update",
    "az network dns",
    "customDomains:",
):
    if prohibited in workflow or prohibited in bicep:
        raise SystemExit(f"Live-copy acceptance crosses a prohibited boundary: {prohibited}")
if ACTIVATION.exists():
    record = json.loads(ACTIVATION.read_text(encoding="utf-8"))
    expected = {
        "schema_version": 1,
        "operation": "accept_live_copy_migration",
        "target_environment": "dev",
        "location": "southcentralus",
        "unique_suffix": "b48224",
        "approval_record": "MD-APPROVAL-AZURE-LEAN-20260904",
        "accepted_release": "release/v3.36",
        "accepted_commit": "63d513605f908d3308bb5dd1bbdbf1061878452b",
        "accepted_image_digest": "salcapadevb48224acr.azurecr.io/salcapa@sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46",
        "candidate_release": "release/v3.110",
        "candidate_commit": "935f0b7bea72375adc936f7904f4f74c2eb99643",
        "candidate_image_digest": "salcapadevb48224acr.azurecr.io/salcapa@sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44",
        "source_server": "salcapa-dev-b48224-pg",
        "temporary_restore_server": "salcapa-dev-b48224-v310-copy",
        "restore_lag_minutes": 15,
        "acceptance_revision": 3,
        "activation_key": "salcapa-v3.110-live-copy-20260910-r3",
    }
    if record != expected:
        raise SystemExit("Live-copy migration activation does not match the exact governed record")

print("SALCAPA_AZURE_LIVE_COPY_MIGRATION_CONTRACT_PASS")
