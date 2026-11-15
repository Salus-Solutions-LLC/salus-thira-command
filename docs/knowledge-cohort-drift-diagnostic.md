# Read-only recovery cohort drift diagnostic

Status: prepared candidate; protected execution and baseline adoption have not occurred.

## Trigger and authority

Approved #1249 merge c0f9a6f3b77dda9976a82cbe41432def14f8c57d ran once as 43756892137, attempt 1. It preserved all four exact receipts at precheck, established two identical complete inventories of 23,747 files, and found zero missing current representation. It stopped at COHORT_BASELINE_DRIFT in preview_metadata before planning writes or commit. Full selected application/worker configuration was unchanged and isolated-job absence verified. See the governed post-search runbook and CURRENT_HANDOFF.md for exact markers, timestamps, hashes and gaps.

The old accepted recovery fingerprint includes represented identities, candidate extraction/archive fingerprints and held-source identities. The historical represented total was 23,632; all 23,747 current files were represented in the failed continuation. Growth alone necessarily changes this projection, but other changes remain unmeasured. Neither an old hash nor matching aggregate counts can reconstruct or prove exact historical 8,404-source membership.

The original #1245 inner failure remains historically unknown: the bounded existing-workspace query was UNAVAILABLE, not an observed PLAN_08. The independently reproduced checkpoint-equality defect and the newly observed baseline-drift stop are distinct.

## Exact authorized candidate scope

New phase salus-cohort-drift-readonly-20261115, original logical target salus-availability-recovery-plan-20261115. This candidate measures current metadata without preparing plans, repeating searches, creating receipts, adopting a baseline, extracting content, resuming retries or holds, or promoting an application image. All authorization flags in its activation are false; database_read_only_required is true.

The new script imports only reusable read helpers from the immutable already approved post-search support source. Both script byte hashes are pinned in the activation and exact pre-Azure guard. The support module has planning functions, but no import-time main execution; the diagnostic never calls those functions. Database-enforced READ ONLY and a separate read-only query facade reject DML, DDL, mutating CTEs, multiple statements and write locks. SQL is static reviewed source. Current evidence queries project scalar metadata, text-presence booleans and hashes; extracted text and raw errors do not leave SQL.

Use two distinct READ ONLY, REPEATABLE READ connections. Each verifies equality of every field in the four original receipts and zero rows for the original target in all three planning tables, including when tables are absent. Each derives the current source partition and projection/core hashes. Both summaries, receipt hashes and full core-invariant hashes must agree before COMPLETE=1 and FRESH_CONNECTION_VERIFIED=1. Scheduling-only extraction/bulk checkpoint changes are counted separately. A missing/changed receipt, existing target row, schema/query failure or core movement fails closed; do not repair, create missing evidence or replay planning.

Published telemetry includes current represented/candidate/legacy-available/exact-text/strict-text/unresolved/held totals; a disjoint seven-category unresolved partition; availability exceptions outside exact-text availability; exact-versus-strict and exact-versus-legacy differences; represented/unresolved count deltas from historical receipts; current represented-set, held-source-set, recovery-projection and core-invariant hashes; overlapping multi-candidate and no-recorded-archive traits; receipt hash; times and scheduling-change counts. No-recorded-archive means candidate rows exist and none has a recorded archive ID; it does not prove bytes are missing. Overlapping traits must not be added to the partition.

Counts and hashes are metadata evidence. They do not qualify content, determine source rights, correlate historical member identities or accept recovery. HISTORICAL_MEMBERSHIP_RECONSTRUCTED=0 and NEW_BASELINE_ADOPTED=0 remain explicit even on diagnostic success. This diagnostic performs no Graph inventory; the last stable inventory pair remains the separate #1249 observation window. It does not query original telemetry again or change logging/access settings.

## Execution and cleanup controls

Protected environment salcapa-dev-approval; merge-triggered activation only; attempt 1 only; no workflow_dispatch. Same diagnostic concurrency group; one isolated manual job, replica retry zero, maximum 900 seconds. Execution uses held immutable v3.276 digest 550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944; accepted app/worker stay v3.223 digest 8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c. No image publication or runtime promotion.

Before/after comparison covers complete selected identity, template and configuration under the same pinned ARM schema 2025-07-01. Cleanup runs even on failure: validate new isolated job tag and image, delete only that job and verify actual absence. Collector tail is bounded at 300; fixed execution state and log-fetch result are printed before success assertions. Retained provider errors remain private. A failed diagnostic is not proof of current counts or receipt preservation at a later window.

Validation: local seven SQLite tests passed, seven dedicated PostgreSQL tests skipped locally. Candidate CI runs all 14 tests with PostgreSQL 16, including the database's own rejection of writes after observation; also validates actual pre-Azure guard against every activation field, second attempt and tampering with either script, all shell blocks and Bicep compilation. CI results must be inspected before exact-head approval.

## Next decision

Run this separately approved read-only candidate once, verify diagnostic markers and cleanup, and record results. Then find retained source-correlated baseline evidence through authorized records. If no baseline membership survives, explicitly retain that coverage gap and obtain a governed prospective-baseline decision rather than describing a new live cohort as the historical 8,404. Build a separately pinned planning candidate only after that reconciliation. The old four receipts remain immutable original-window evidence throughout.

## Search and capture coverage

Reuse the four verified task search receipts; no fifth receipt or duplicate search is created. Repository governing records, approved scripts, run evidence and the current chat approval were inspected. The prior task search/capture document retains connected-source search coverage and gaps; this diagnostic is an evidence follow-up, not a claim of fresh exhaustive search across every location. Code remains authoritative in GitHub without a second Library source copy. Universal chat/work-chat export and original historical-log coverage remain unresolved.
