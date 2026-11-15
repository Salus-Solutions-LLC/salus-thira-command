# Knowledge availability reconciliation and recovery batch preparation

Status: PR #1245 exact approved head merged as 1ca19fed9ab818868956479ab59108414ae8e2a4. Protected run 43743532577 failed without usable task results; runtime/cleanup passed. Receipt and plan outcome remains unverified. Do not replay this consumed operation. See docs/knowledge-recovery-receipt-readback.md for the confirmed invalid log-tail setting and proposed read-only reconciliation.

## Objective and authority

Reconcile the five legacy-available sources lacking exact extraction Complete/nonempty-text evidence, and prepare a version-bound recovery worklist for the 8,404 distinct service-unresolved sources. SAL-D116, SAL-D118, SAL-D119, SAL-D125, SAL-D133 and SAL-D134 apply. This is an internal operational runbook, not a qualified client report.

Authoritative baseline: protected census run 43714532410, merged source 95782daf91e6161209db94e3d231d8ea663b3041 and accepted handoff merge e73c6b5d8b699a32ccfee115aa6c3279df0571a3. Preparation inspected the five current governing records at a23ff0ded4535688690b0341d2f24c8d9e1aaad9 and preserves concurrent PR #1242.

Baseline: 23,622 physical files, 23,632 represented, 15,228 legacy-available, 15,223 exact Complete/nonempty text, five availability exceptions and 8,404 service-unresolved. The five availability exceptions are outside that 8,404; the five conflicting sources are inside it. Exact-text complement 8,409 is not a revised historical receipt.

| Disjoint unresolved source cohort | Expected sources | Required next gate |
|---|---:|---|
| Governed extraction review | 7,085 | Qualified source review; safe separately retained derivative/remedy |
| Retry paused | 733 | Validated processor-specific release before any resumption |
| Automatic retry | 488 | Same-candidate archive/hash, due and lease preflight; separately approved bounded batch |
| Governed hold | 93 | Source-owner/authority disposition; retain hold |
| Other or conflicting | 5 | Reconcile every version and its checkpoint/permissions |
| No candidate or Complete without text inside this subset | 0 | Stop on changed cohort |

The 26 multiple-candidate sources and 38 without an archive item recorded are overlapping traits. An empty archive field is not proof an object is missing. Failure-code rows are candidate-level; the operation builds the actual category/code/checkpoint cross-matrix rather than multiplying independent totals.

## Exact scope

The activation permits only four new task-specific consideration receipts and three additive recovery-ledger tables: m365_knowledge_recovery_plans, m365_knowledge_recovery_batches and m365_knowledge_recovery_plan_events. It does not update candidate, hold, source, event, cursor or retry/checkpoint rows. Source schema changes remain forbidden. Recovery-ledger DDL and all batch/manifest/audit inserts are atomic.

A new task key salus-availability-recovery-plan-20261115 prevents reuse of the consumed successful census actor. No workflow_dispatch; merge-triggered activation is single-attempt and protected by salcapa-dev-approval. The operation shares the existing knowledge-diagnostic concurrency group.

Runtime remains v3.223, app and worker digest 8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c. The isolated job uses published immutable v3.276 digest 550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944, source release/v3.276 at 7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3. It runs reviewed script bytes, not a changed application image. No application promotion, permissions, Protected Member access, qualification, assignment or release is included.

## Evidence and reconciliation

1. Reject any existing receipt or plan for this operation. Establish two consecutive identical full-root metadata inventories, within three initial observations, with all seven governed areas, ancestry, provenance and pagination guards.
2. Check complete current membership and bind the unresolved snapshot to accepted SHA-256 7836ad36e47829cdf3bf34ae269d5868017cee39759ae314da6912f0945ac3a9. If identities, statuses, hashes or availability conditions drift, stop; do not silently replace the approved historical cohort. Current physical totals may grow only if all current membership is represented and the approved represented recovery snapshot is unchanged.
3. Project exact extraction status, text-type/nonempty booleans and the legacy match from SQL. Never select extracted text or free-text extraction errors. Bind full classification bytes through an in-database SHA-256 without emitting contents.
4. For each of the five exceptions, retain every candidate ID, source eTag/SHA-256, archive metadata, current-source version match, checkpoint and exact condition in the restricted database manifest. A legacy Complete match on a non-Complete extraction and an exact Complete label with empty text receive different fixed diagnoses. Missing archive evidence and historical/current version conflicts stay explicit.
5. Compare the accepted exact predicate to a typed-string, explicit-whitespace predicate. Stop if compact-JSON false negatives, whitespace-only or nonstring text reveal additional discrepancies. Do not presume the five share the same cause.
6. Enumerate each of the 8,404 unresolved sources exactly once. Keep every candidate version and its failure code, retry flags, disposition, archive references/hash/eTag, review state, attempts, next-attempt, lease, checked time and last code. Include applicable hold reasons/rights dispositions and bulk checkpoint evidence. Mark missing checkpoints, absent archive metadata, historical-only/current-version mismatch, live leases and multiple versions.
7. Partition by cohort, exact failure-code signature, archive/current-version evidence, lease and multiple-version traits; split into batches of at most 50 distinct sources. Mixed candidate versions stay together. All plans and batches are Prepared - Not Authorized for Processing and Unvetted Candidate. None is automatically executable or a finding that archived bytes were verified.
8. Run four fresh task-specific corpus searches below using unchanged deployed-service semantics, preserve original receipts, and prove complete live represented consideration. Search result previews remain internal; lexical matches do not qualify evidence.
9. Recheck the complete inventory before committing. Take NOWAIT SHARE locks on candidate, hold, bulk and checkpoint tables, with a two-second lock timeout and 30-second statement timeout. Under those locks, require exact equality of all selected evidence to the pre-search snapshot. Ordinary readers remain available; an in-flight source writer causes a safe stop. Only the short additive ledger transaction holds these locks, never the multi-minute remote inventory/search.
10. Atomically store canonical per-batch JSON/hash, one manifest containing exact batch hashes and the five restricted exception records, and one plan-level audit event. Roll back all new planning DDL/rows on failure. Preserve old receipts even if the later planning step fails.
11. From a fresh database connection, compare the exact manifest, every batch payload/count/hash, audit event, actor/timestamp/count of all four receipts, and unchanged source evidence. Report fixed-code aggregate conditions, overlap counts, real candidate cross-matrix, plan hashes and explicit completion markers only.

The deployed availability service currently uses a broad classification JSON LIKE predicate. This operation reconciles that count with exact source-correlated evidence and records the five as availability exceptions. It does not deploy a prospective service predicate fix or repair/extract their contents. A separate exact-version service correction and regression-tested immutable release is the next gate after the actual five conditions are known. Historical receipts remain immutable.

PostgreSQL semantics were checked against the primary [explicit locking documentation](https://www.postgresql.org/docs/current/explicit-locking.html) and [JSON functions documentation](https://www.postgresql.org/docs/current/functions-json.html). In particular, the JSON path extracts the extraction field itself; SHARE conflicts with source writers. Real PostgreSQL CI must verify this implementation, including a concurrent writer rejection.

## Task-specific search

| Label | Query |
|---|---|
| availability_reconciliation | extraction availability complete text provenance archive version discrepancy |
| recovery_batches | governed recovery review retry paused processor failure checkpoint batch |
| safety_and_contrary | hold restrictions source rights conflict unsafe document original derivative |
| verification | recovery manifest audit receipt stability cleanup independent verification |

No current-task corpus receipt exists during candidate preparation; accepted prior-task receipts are supporting evidence only. The exact operation creates and independently reads back its own four receipts after approval. Other authorized location search and chat-capture gaps are recorded in docs/knowledge-recovery-search-capture-20261115.md.

## Verification and cleanup

PR validation compiles both Python files, runs the SQLite fixtures, checks every workflow shell block with bash -n, runs the actual pre-Azure guard against the real activation, mutates each guarded field, rejects attempt 2 and altered script bytes, and compiles Bicep. A separate postgres:16 CI service exercises actual JSON paths/hashes, rollback, durable independent readback, mutation detection and a concurrent source writer. SQLite tests additionally deny all source-table writes.

The protected job requires all census/search/fresh-receipt markers plus RECOVERY_PLAN_PREPARATION_COMPLETE=1, RECOVERY_PLAN_FRESH_CONNECTION_VERIFIED=1, RECOVERY_PLAN_PREPARED_SOURCES=8404, RECOVERY_PLAN_AVAILABILITY_EXCEPTIONS=5 and RECOVERY_PLAN_RETRIES_RESUMED=0. A workflow success alone is insufficient: inspect the exact plan/receipt markers and cleanup separately.

The isolated job is salcapa-recovery-plan-b48224. Verify namespace absence before creation; cleanup checks its task tag and immutable image before deletion, then lists jobs to prove absence. Compare complete selected app and worker identity/template/configuration through pinned ARM API 2025-07-01 before and after, suppressing no selected field. Preserve the durable receipts and recovery plan; deleting evidence is not cleanup. Record source/batch/receipt hashes, run/jobs, completion times, runtime comparison and actual resource-absence proof in CURRENT_HANDOFF.md.

If partial receipts or a committed plan exist after any later failure, stop and inspect them read-only; never rerun attempt 2 or invent another operation key to bypass duplicate detection. Any successor requires reconciled pre-state and separate exact-head authorization.

## Fixed planning failure codes

All unexpected errors remain UNEXPECTED_FAILURE with a fixed stage; no exception string is logged.

| Code | Meaning |
|---|---|
| PLAN_01 | Recovery evidence resource bound exceeded |
| PLAN_02 | Candidate outside represented boundary |
| PLAN_03 | Availability comparison changed; review successor scope |
| PLAN_04 | Recovery cohort changed; review successor scope |
| PLAN_05 | Recovery membership does not reconcile |
| PLAN_06 | Plan evidence binding disagrees |
| PLAN_07 | Recovery manifest storage bound exceeded |
| PLAN_08 | Recovery evidence changed before manifest commit |
| PLAN_09 | Recovery operation already recorded; no replay |
| PLAN_10 | Injected transaction failure fixture |
| PLAN_11 | Recovery manifest durable readback disagrees |
| PLAN_12 | Recovery batch count disagrees |
| PLAN_13 | Recovery batch exact readback disagrees |
| PLAN_14 | Recovery audit event readback disagrees |
| PLAN_15 | This operation has receipts; inspect instead of replaying |
| PLAN_16 | This operation has a durable plan; no replay |
| PLAN_17 | Accepted recovery cohort changed; prepare a successor scope |
| PLAN_18 | Task receipts disagree with recovery snapshot |
| PLAN_19 | Source inventory changed before recovery manifest commit |
| PLAN_20 | Recovery evidence changed after manifest commit |

## Next recovery work after verified preparation

1. Review the actual five candidate-correlated diagnoses and prepare the smallest service-count/preview correction, preserving immutable receipts and qualification controls.
2. Have the governance/source owner review hold and conflicting-version batches and the archive/checkpoint gaps; no data deletion or exclusion.
3. Select a small processor-specific batch, test the remedy on safe fixtures and verify archive bytes/SHA-256 under its separately approved execution. Active, legacy, encrypted, malformed and unsupported sources require appropriate human review or a distinct safe derivative; never relax existing extraction controls.
4. Keep all 733 retry-paused obligations paused until their validated processor release. Do not bulk-run the 488 automatic-retry records from this planning activation.
5. For each future batch, freeze exact membership/pre-state and authority, preserve original/provenance, record derivative hashes and audit events, prove durable transitions and cleanup, and reconcile resolved/new/changed/held/failed counts against a new stable census.
