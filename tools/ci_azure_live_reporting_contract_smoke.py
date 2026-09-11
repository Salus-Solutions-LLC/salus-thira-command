#!/usr/bin/env python3
"""Fail-closed contract checks for isolated Azure live-reporting acceptance."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "azure-live-reporting-acceptance.yml"
BICEP = ROOT / "infra" / "azure" / "live-reporting-acceptance.bicep"
SCRIPT = ROOT / "tools" / "azure_live_reporting_acceptance.py"
ACTIVATION = ROOT / "deploy" / "azure" / "activations" / "live-reporting-dev.json"
SCRIPT_SHA256 = "01ed44ae0fe283e123115a9192e96a4ce75bb8345529b9d7e688be874d2b8586"


def require(value: str, content: str) -> None:
    if value not in content:
        raise SystemExit(f"Live-reporting acceptance contract is missing: {value}")


workflow = WORKFLOW.read_text(encoding="utf-8")
bicep = BICEP.read_text(encoding="utf-8")
script = SCRIPT.read_text(encoding="utf-8")
assert hashlib.sha256(SCRIPT.read_bytes()).hexdigest() == SCRIPT_SHA256

for value in (
    "deploy/azure/activations/live-reporting-dev.json",
    "environment: salcapa-dev-approval",
    "permissions: {}",
    "needs: authorize",
    "id-token: write",
    "ref: release/v3.111",
    "8bf4614ec79a27641c40dc1a21e1790746a08604",
    "63d513605f908d3308bb5dd1bbdbf1061878452b",
    "sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311",
    "sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46",
    SCRIPT_SHA256,
    "accept_live_reporting",
    "salcapa-dev-b48224-v311-report",
    'JOB_NAME="salcapa-dev-b48224-v311-rpt"',
    "restore_lag_minutes == 15",
    "trap cleanup EXIT",
    "az postgres flexible-server restore",
    "az deployment group create",
    "LIVE_REPORTING_ACCEPTED",
    "Source database and running application configuration: unchanged",
    "Human authority: simulated only for this isolated acceptance",
    "Application deployment, traffic shift, DNS change, password, and client secret: none",
):
    require(value, workflow)

for value in (
    "temporary-live-reporting-acceptance",
    "var jobName = '${stem}-v311-rpt'",
    "@secure()",
    "acceptanceScriptBase64",
    "image: imageDigest",
    "runtimeIdentity.id",
    "SALUS_POSTGRES_HOST",
    "restoredPostgresHost",
    "SALUS_POSTGRES_AUTH",
    "managed_identity",
    "SALUS_AUTH_MODE",
    "local",
    "SALUS_OIDC_AUTO_PROVISION",
    "SALUS_SEED_DEMO",
):
    require(value, bicep)

for value in (
    '"Draft"',
    '"Released"',
    "Client Executive",
    "Protected Member Viewer",
    "Lead Assessor",
    "System Administrator",
    "Assessment Director",
    "executive.csv",
    "executive.html",
    "industry_defaults_snapshot_json",
    "Isolated unreleased change marker",
    "status_code == 409",
    '"LIVE_REPORTING_ACCEPTED"',
    '"cross_member_denied": True',
    '"released_snapshot_immutable": True',
    '"human_release_authority_simulated_for_isolated_acceptance_only": True',
):
    require(value, script)

trigger_prefix = workflow.split("permissions:", 1)[0]
for prohibited in ("pull_request:", "workflow_dispatch:", "schedule:"):
    if prohibited in trigger_prefix:
        raise SystemExit(f"Live-reporting acceptance may not expose {prohibited}")
for prohibited in (
    "AZURE_CLIENT_SECRET",
    "POSTGRES_PASSWORD",
    "SALUS_DATABASE_URL",
    "az containerapp update",
    "az network dns",
    "customDomains:",
):
    if prohibited in workflow or prohibited in bicep:
        raise SystemExit(f"Live-reporting acceptance crosses a prohibited boundary: {prohibited}")

record = json.loads(ACTIVATION.read_text(encoding="utf-8"))
expected = {
    "schema_version": 1,
    "operation": "accept_live_reporting",
    "target_environment": "dev",
    "location": "southcentralus",
    "unique_suffix": "b48224",
    "approval_record": "MD-APPROVAL-AZURE-LEAN-20260904",
    "accepted_release": "release/v3.36",
    "accepted_commit": "63d513605f908d3308bb5dd1bbdbf1061878452b",
    "accepted_image_digest": "salcapadevb48224acr.azurecr.io/salcapa@sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46",
    "candidate_release": "release/v3.111",
    "candidate_commit": "8bf4614ec79a27641c40dc1a21e1790746a08604",
    "candidate_image_digest": "salcapadevb48224acr.azurecr.io/salcapa@sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311",
    "acceptance_script_sha256": SCRIPT_SHA256,
    "source_server": "salcapa-dev-b48224-pg",
    "temporary_restore_server": "salcapa-dev-b48224-v311-report",
    "restore_lag_minutes": 15,
    "acceptance_revision": 1,
    "activation_key": "salcapa-v3.111-live-reporting-20260910-r1",
}
if record != expected:
    raise SystemExit("Live-reporting activation does not match the exact governed record")

print("SALCAPA_AZURE_LIVE_REPORTING_CONTRACT_PASS")
