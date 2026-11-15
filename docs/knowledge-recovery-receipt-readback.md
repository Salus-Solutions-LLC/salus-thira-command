# Recovery receipt readback after log-collection failure

Status: candidate; no readback activation has run. Exact-head approval is required.

PR #1245 approved head 0c42e7520c911e0b9a7e3f4d0585c223e79e3393 merged as 1ca19fed9ab818868956479ab59108414ae8e2a4. Its protected run 43743532577, attempt 1, failed its task step at 18:06:43 UTC on 15 November 2026. Approval job 132901713297 and exact-script gate passed; task job 132901743332 failed. The retained log has no actual inventory, receipt or plan completion markers. Echoed shell source is not execution evidence.

Cleanup passed independently: TASK_KNOWLEDGE_APPLICATION_AND_WORKER_UNCHANGED=1 at 18:06:44.9708053 UTC and TASK_KNOWLEDGE_ISOLATED_JOB_REMOVED=1 at 18:07:06.5726673 UTC. These are 12:06:44 and 12:07:06 CST. Cleanup compared complete selected app/worker identity, template and configuration under pinned ARM API 2025-07-01, then checked task tag/image, deleted the isolated job and verified absence. Accepted runtime remains v3.223 at digest 8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c.

The collector requests --tail 600. The primary [Azure CLI documentation](https://learn.microsoft.com/en-us/cli/azure/containerapp/job/logs?view=azure-cli-latest) permits 0–300. Under set -e, its redirected log-fetch error can terminate the step before the safe marker output. The exact suppressed CLI error text was not retained, so record this confirmed collector defect without asserting the hidden job status or excluding another earlier failure. The original underlying execution may have written no, partial or complete permitted evidence.

Do not replay run 43743532577, change its task key to bypass duplicate checks, recreate evidence or assume zero writes from missing logs. The exact five diagnoses, new four-receipt outcome and durable 8,404-source batch outcome remain unknown until read back.

## Source correction

The original recovery-planning workflow now uses --tail 300, safely reports a fixed execution-state enum and numeric log-fetch exit before any success assertion, and retains privacy-safe markers even when collection fails. Raw CLI error output is not published. The consumed original activation and its planning script remain unchanged; this workflow correction does not trigger another original run because its push trigger is activation-file-only.

The new readback workflow uses the same correction, protected approval environment, immutable execution image, runtime prechecks/comparison and scoped cleanup controls. CI executes the actual collectors with a CLI fixture enforcing the Azure tail limit and checks both success and private-error failure paths. It also executes the actual pre-Azure binding guard, rejects altered fields, attempt 2 and modified script bytes, checks all shell blocks and compiles Bicep.

## Read-only operation

New task key: salus-availability-recovery-readback-20261115. Original target operation: salus-availability-recovery-plan-20261115. Original run: 43743532577.

Use already published isolated execution digest 550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944 from frozen release/v3.276 at 7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3. The app/worker remain on the accepted v3.223 digest above. The isolated job is salcapa-recovery-readback-b48224 with 360-second replica limit, zero replica retry, one replica, unchanged existing identity and no new access grants.

The script opens a PostgreSQL REPEATABLE READ, READ ONLY transaction, with a 60-second statement timeout. It selects only the original task's existing consideration receipts, planning manifest, batches and plan audit event. Missing planning tables are observed, never created. It does not import the consideration service or application initializer, execute DDL/DML, scan source content, write a new receipt, resume a retry, alter a hold, qualify evidence or publish anything.

Readback checks:
- Zero/partial/complete receipt states remain distinct. Each present receipt must have the exact original actor label/query hash, valid unique ID/time and accepted count relations.
- A complete preparation needs four correct receipts, exactly one manifest/event, canonical JSON and matching manifest/batch hashes, correct state/time, every batch of at most 50, and every one of the 8,404 sources exactly once across the disjoint approved categories.
- All five availability exceptions must be separate from those 8,404. Verify same-source candidate linkage, exact condition booleans/counts, Unvetted Candidate state and no processing authority. Preserve all version/archive/checkpoint metadata; a hash verifies retained metadata, not original bytes.
- Recompute category membership from retained extraction statuses/holds and compare the audit event exactly.
- Close the first connection, open another READ ONLY transaction, and require an identical result. Emit bounded fixed telemetry, receipt IDs/hashes/counts/times and aggregate plan evidence only.

Outcome meanings:
- EMPTY: no original-task receipt/plan/batch/event observed; planning is not complete.
- PARTIAL_RECEIPTS: some or all consideration receipts exist without a committed plan; planning is not complete.
- COMPLETE_PREPARED: the committed plan, all batches/event and four receipts passed independent readback. This establishes retained preparation as of the manifest timestamp, not success of the original workflow, a new stable current-source census, extraction, qualification or authority to execute batches.
- Corrupt, orphan, inconsistent, changed-between-connections or unsupported state: fail closed with a fixed stage and preserve evidence.

RECOVERY_READBACK_COMPLETE=1 means this read-only reconciliation completed. RECOVERY_READBACK_COMPLETE_PREPARATION_VERIFIED is a separate zero/one result; never equate them. Required write/replay markers are DATABASE_WRITES=0, NEW_SEARCH_RECEIPTS=0 and ORIGINAL_TASK_REPLAYED=0.

## Search, capture and next steps

The original task's four exact queries and search/capture boundary are retained in docs/knowledge-recovery-search-capture-20261115.md. This readback deliberately creates no duplicate task receipts. Verify any original receipts before claiming that task's corpus consideration; if absent/partial, carry the explicit search gap to a separately approved successor. An SQL ledger readback is not a new full-source inventory or universal chat ingestion.

After this candidate is checked and approved at its exact head, run it once, verify observed durable state and cleanup separately, and update CURRENT_HANDOFF.md. If a complete plan exists, preserve it and use a fresh per-batch preflight for any separately authorized recovery; do not recreate it. If empty/partial, diagnose the missing phase and prepare a new bounded planning/search proposal from that observed pre-state. Keep all retry pauses, holds, source rights and Protected Member boundaries intact. Future service availability correction still requires its own reviewed immutable release after actual diagnoses.

## Separate Python question

User asked whether PR #1243's Python 3.12-to-3.15 change should be performed. Read the exact one-line Dockerfile patch and check run 43719551266 at head 7c14b777c12c8a627092f9666e593b0673215652. Container job 132828346173 failed to install psycopg-binary==3.3.4 on Python 3.15; validation job 132828346394 reported 17 audit findings in PyJWT/opentelemetry-api. Those are that PR's older checks, not a statement about the accepted deployment or current branch: current merge CI 43743532512 passed build, validation/audit and PostgreSQL runtime.

The [Python support table](https://devguide.python.org/versions/) lists 3.12 security support through October 2028 and 3.15 in bugfix support; [3.15.0 is a stable release](https://www.python.org/downloads/release/python-3150/). Recommendation: retain the accepted runtime, refresh the separate upgrade candidate against current requirements, resolve compatibility/audit issues and require successful build/runtime checks before exact-version promotion. PR #1243 remains open/unmerged; no rebase command, dependency change or upgrade was authorized or performed.
