# Stable Knowledge census diagnostics

Status: governed successor candidate; live cause and acceptance remain unverified.

## Problem and evidence

PR #1231's one approved run, 43678462983, found all 23,622 enumerated source files represented, with zero missing in every governed area. It then reported RuntimeError at stable_source_prewrite, zero new receipts and no committed batch. Runtime comparison and isolated-job removal passed.

The previous reader used the same exception type and stage for a failed second inventory and a completed-but-unequal inventory. It retained neither the specific guard nor aggregate differences. The original live cause cannot be recovered from those markers. This successor fixes that demonstrated diagnostic defect; it does not retroactively prove a Graph error, source drift, parser defect or worker cause.

## Reader and comparison

Preserve complete root-scoped Graph delta enumeration, all continuation pages, last-occurrence handling, exact seven-area/drive/ancestry checks, source version/size provenance, shortcut rejection and existing resource bounds. Microsoft documents full initial delta enumeration and following every continuation, and cautions that the last returned occurrence represents the item's latest state and that some properties can be omitted. These facts guide tests; they are not evidence of this live failure's cause. [Microsoft Graph delta contract](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0).

Use a fixed failure-code vocabulary for root/page HTTP/request/JSON/payload failures and scope, parentage, type, provenance, pagination and metadata-helper validation. Never log response bodies, URLs, tokens, names, paths, ownership or raw exceptions. Unknown exceptions become UNEXPECTED_FAILURE.

Every completed inventory emits only file count, UTC completion time and canonical snapshot hash. Comparing two completed inventories emits aggregate added/removed/changed counts and overlapping version, size, parent/area, name, path, modified-time, content-tag, MIME, attribution, trusted-URL and other-field categories. Preserve comparisons of every captured field, including unknown future fields and serialization differences. Never normalize away a difference. Category counts overlap and must not be summed as distinct files.

A failed inventory is not a completed observation and is not retried. For complete but changing inventories, allow at most three full read-only observations inside the one execution. Require two consecutive exact-equal inventories before proceeding; use that measured stable pair's current baseline. Continuous changes stop with STABILITY_NOT_ESTABLISHED. This bounded convergence is not processing retry, activation replay or permission to accept unequal snapshots.

## Receipt-only operation

This successor cannot enroll metadata, create reconciliation audit tables, change sources, pause normal intake, lift holds, restart retries, change permissions, assign a Protected Member or release content. It checks prior census/reconciliation/current-task receipt counts and the prior enrollment-batch state durably before searching. Existing evidence stops the operation for reconciliation.

After a stable pair, require zero missing current source IDs in the complete represented union. A renewed gap fails closed. Preserve the accepted historical minimums, but bind counts to the live census. A zero-gap checkpoint alone is not census acceptance.

Run four new task-specific corpus searches. Full inventories before and after those searches must still exactly equal the established source baseline; later changes block completion and any created receipts remain explicit partial evidence. Require represented=considered and full match/no-match/availability reconciliation. Verify each original query hash, actor, timestamp and coverage field using a separate database connection after service commits, and require exactly four operation receipts. Keep recovery-metadata fingerprints stable across the search.

Report broad service Complete-based availability separately from exact extraction-status/nonempty-text evidence. Metadata coverage and apparent text availability do not resolve original-content, human qualification, source rights or customer release obligations.

## Protected execution and evidence

Use the already-published immutable v3.276 image at sha256:550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944, frozen source 7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3. Its database, intake and consideration modules have identical repository blob IDs to the prior diagnostic image source. This adopts the published patched image for the isolated job only; it does not deploy the application or worker. The accepted runtime precondition remains exact v3.223.

Retain protected-environment approval, shared diagnostic concurrency, exact script hash and activation, 900-second isolated job and zero retries. No workflow_dispatch or consumed-activation replay is introduced.

Emit safe diagnostic markers before asserting success. Retrieve 300 log lines, within the CLI's documented limit, so bounded observation and receipt evidence fit the capture. Retain approved aggregate markers in GitHub logs; raw inventories remain private in memory. [Azure job-log contract](https://learn.microsoft.com/en-us/cli/azure/containerapp/job/logs?view=azure-cli-latest).

Compare full selected application/worker identity/configuration/template fields using identical pinned ARM API 2025-07-01, with no suppressed differences. Delete only the task-tagged/image-bound isolated job and verify absence independently of diagnostic success. Any runtime-prestate drift stops execution.

## Acceptance and next actions

Exact-head CI and Marc's approval precede one protected execution. Acceptance additionally requires the stable pair, zero current representation gap, unchanged complete inventories throughout the four searches, four separate-connection-verified durable receipts, stable recovery metadata, unchanged runtime and verified isolated-job absence.

If a guard fails, record the fixed code, completed/attempted observation counts, actual aggregate differences and any partial receipt IDs. Diagnose that evidence before another protected action. Source-owner coordination or a processing/configuration change is a separate governed decision, never an automatic response to a mismatch.

Update CURRENT_HANDOFF.md with source/merge/run, measured cause or remaining uncertainty, every receipt/partial/zero disposition, census/recovery counts, cleanup/runtime proof, owner and next recovery step. Only measured current recovery groups can select later processor-specific batches; the old 7,923 remains historical.
