# Bounded recovery of read-only inventory verification

Controlled candidate, 16 November 2026. This version changes Azure monitoring and collection only. The five-module reconciliation payload, SQL read-only controls, twenty-receipt proof, inventory/source limits and result-validation function remain unchanged from approved PR #1284.

## Confirmed failure and limits

PR #1284 exact head `f1c3b5294bbb3ad226454531e6c1d8dca55d1f28` merged as `412764b94c260a7fdea1713c641d0e9d6af57e45`. Run 43935027835 attempt 1 returned Azure “Too Many Requests” at 19:06:10 UTC (13:06:10 CST). The shell exited before terminal status and console-log collection. The retained log does not isolate the exact Azure command or establish whether the reconciliation payload started or how far it progressed. Do not claim a fresh receipt proof, stable inventory, source reconciliation or database readback from this attempt.

Full selected app/worker identity/template/configuration equality passed at 19:06:11 UTC (13:06:11 CST). The task-tagged isolated job was deleted and independently listed absent at 19:06:31 UTC (13:06:31 CST). All fourteen other executed merge checks passed. The twenty prior receipts and existing baseline/plan/remediation/review manifests remain the last verified authority. The pinned payload has no data-write path; no new receipt, baseline adoption, proposal preparation, source bytes, processing or retry/hold change was authorized. Fresh operational verification remains unfinished.

The wrapper's error handling permitted a throttled management request to skip diagnostic collection while cleanup still ran. This candidate adds bounded GET retry and an always-run collector before cleanup. It does not assert a cause for the service's throttling, reconstruct unretained runtime output or replay the failed workflow.

## Exact-version gate and unchanged payload

Use a new activation and workflow for one separately approved attempt 1. Keep the old workflow, activation and historical run immutable. New wrapper operation: `salus-readonly-inventory-reconciliation-recovery-20261116`; original reconciliation operation remains `salus-readonly-inventory-reconciliation-20261116` inside the unchanged payload.

The main script SHA-256 remains `08ee4532f2fbd96a409ec0d6cb7f6117dcc85e3d712b8d0427f3948654c9ea97`; payload SHA-256 remains `86e9fdbdcfb307adcb6a5ea2bc19fcae9be45f93123cd651b650fffd90003274`. The activation binds eleven source hashes, six governing rows, the prior failed run and fixed transport budgets. Exact-version human approval is required before merge/isolated execution. No general approval, baseline adoption or method qualification is inferred.

## Transport and action separation

The new helper issues only authenticated HTTPS GET requests to the specified `rg-salcapa-dev` Microsoft.App/Microsoft.Resources management endpoints and approved API versions. It rejects other hosts, resource groups/providers, unsupported query parameters, redirects and write methods. It obtains the existing Azure-login token in memory, does not persist it, and prints only fixed sanitized status/retry codes. Access denials and authentication errors are not retried or bypassed.

Retry only GET requests for 429 or specified transient server/network failures: at most five requests per read, a 120-second read budget, a 30-second per-request timeout and an 8 MiB response bound. Respect `Retry-After` numeric/date values and bounded exponential delay. If the requested delay does not fit the remaining budget, stop and defer; do not retry earlier than the service instructed. Deployment polling is limited to 600 seconds; the single job execution's monitoring deadline is 960 seconds, including recovery collection. The resource still has the unchanged 900-second execution limit, zero execution retries, 0.5 CPU/1 GiB and 786,432 KiB payload memory guard. This observation deadline does not extend source processing or container runtime authority.

Submit the deployment once using `--no-wait`, then use bounded GET monitoring. Invoke job start once. Never automatically repeat either submission/start command after an ambiguous response. Export an execution name and shared deadline when available. If start acknowledgement is missing, the collector may discover a single existing execution belonging to the new, task-tagged namespace; zero or multiple executions fail without another start. No write request is issued by the transport helper.

Stage markers identify runtime precheck, deployment submission/polling, job start, execution polling, terminal readback, console-log collection and cleanup. The execute step may fail without skipping the collector. It is not sufficient for the execute step to be marked complete: the final collector and cleanup determine success from retained evidence.

## Always-run terminal collection and cleanup

Run terminal collection before cleanup even if submission or monitoring failed. Require the task-owned job and exact image, use the known or uniquely discovered execution, and continue only read-only monitoring within the original deadline. Retain sanitized platform status/exit/OOM evidence and attempt console-log collection independently of the initial monitor's result. A full successful payload report, terminal Succeeded status, result validation and cleanup are mandatory for a successful governed outcome. Missing, throttled or ambiguous evidence remains a qualified failure; no success is inferred from job absence.

The unchanged report validator requires all twenty receipts, empty failed/current outputs, exact stable inventory samples/final equality, bounded hashed source deltas, approved-scope and protected pause/hold/checkpoint readback, and zero writes/receipt creation/baseline adoption/proposal preparation/source access/processing. All historical reconstruction and content/capture/qualification limits remain in force.

Cleanup always compares full selected ARM app/worker identity/template/configuration, using the bounded GET helper for final reads. Delete only the correctly tagged isolated `salcapa-invrecover-b48224` job with the expected image, then independently list absence. Preserve v3.223 runtime, the personal SalusScan2 email opt-out, paused retries and holds, Compass pause and disabled reader. A cleanup failure must remain open; this candidate does not authorize deleting another resource.

## Validation and next steps

Test GET-only retries, numeric/date Retry-After, exhausted budgets, denials, redirect blocking, token/output redaction, unique execution discovery, no repeated submit/start, shared deadline, unchanged payload/report validation, always-run collector ordering and cleanup ownership. Run the unchanged real PostgreSQL reconciliation tests, the actual pre-Azure guard, shell syntax and Bicep build before requesting exact-version approval. Record measured results and remaining limits in the handoff after the approved run. Any later repair, baseline proposal, method adoption, source selection, preflight or processing remains separately gated.

Primary guidance: [Azure Resource Manager throttling](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/request-limits-and-throttling) specifies 429 and Retry-After handling; [Azure CLI group deployment](https://learn.microsoft.com/en-us/cli/azure/deployment/group#az-deployment-group-create) documents `--no-wait`; [Microsoft.Resources deployment version reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.resources/2022-09-01/deployments) identifies the pinned deployment API version. These are bounded design references, not proof of the failed request's exact cause or exhaustive research.
