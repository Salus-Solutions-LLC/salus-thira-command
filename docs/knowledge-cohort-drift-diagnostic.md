# Read-only recovery cohort drift diagnostic

Status: approved #1252 merged and executed once; read-only diagnosis and cleanup accepted. No baseline adopted and no batches prepared.

## 15 November 2026 Central — Read-only cohort diagnostic accepted; 8,430 current unresolved records, four original receipts preserved, no planning writes

**Authorized version and execution.** Marc explicitly approved PR #1252 exact head `1560eaf93e4755925b597790ca5e132f50f16cd3` for merge and one read-only diagnostic. Refreshed the five governing records at `074c8557221b977d00071b744b6c424788687d4b`; all eight applicable exact-head checks passed across five workflows, including all 14 diagnostic tests under PostgreSQL 16 and actual guard rejection of all 28 activation fields, attempt 2 and tampering with either script. Squash merge `640d54cf71d053e0731ef3990eb4ab16dec3eac6` preserved all six diagnostic assets exactly. The merged handoff retained the full approved recovery text plus the concurrent SAL-D135 document-standards section from #1253 / `fe726ebc99e5f3264417172f5fc7cf445c48ef63`; its insertion was the only handoff difference. Refreshed all five records again after merge and retained that concurrent policy work. No diagnostic/source execution assets changed.

Protected run [43761349512](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/43761349512), attempt 1, executed that merge. Approval job 132956641515 and task job 132956675253 succeeded. The diagnostic script SHA-256 is `d346adb6a2037de502905754ce641b52526f7127f4629386849ca7dd85d7175f`; pinned support source SHA-256 is `2bfaf1b5c16c6a66f77bd69c61dec7a36afc6cefe3c9b7f67795972586d0ee49`. This accepts the bounded read-only diagnosis and cleanup, not recovery preparation, source qualification, processing or release.

**Two independent current metadata snapshots.** Separate READ ONLY, REPEATABLE READ connections completed at 21:04:16.259476 and 21:05:16.354199 UTC on 15 November 2026 (15:04:16 and 15:05:16 CST). Both agreed on every emitted summary and the full source/authority invariant hash. FRESH_CONNECTION_VERIFIED=1 and COMPLETE=1. Extraction and bulk scheduling-change counts were both zero. Current represented sources total 23,757; candidate rows total 23,731. The historical receipts represented 23,632: net represented-count change +125. These are represented identities, not candidate-row or physical-file counts.

| Current source observation | Historical receipt/census window | Current diagnostic | Net count change |
|---|---:|---:|---:|
| Represented | 23,632 | 23,757 | +125 |
| Legacy service-available | 15,228 | 15,327 | +99 |
| Exact Complete with nonempty text | 15,223 | 15,322 | +99 |
| Metadata-only or unresolved by legacy predicate | 8,404 | 8,430 | +26 |
| Availability exceptions outside exact Complete/text set | 5 | 5 | 0 |
| Governed held sources | 93 | 93 | 0 |

Current exact and strict string/non-whitespace text sets both contain 15,322 sources; their symmetric difference is zero. Exact-but-not-legacy count is zero. Therefore 23,757 = 15,327 + 8,430; the exact-text complement is 8,435, comprising 8,430 legacy-unresolved plus five separate availability exceptions. Availability and text presence remain metadata evidence, not proof the task read or qualified all source content.

| Disjoint unresolved category | Historical window | Current | Net count change |
|---|---:|---:|---:|
| Governed review | 7,085 | 7,085 | 0 |
| Retry paused | 733 | 733 | 0 |
| Automatic retry | 488 | 512 | +24 |
| Governed hold | 93 | 93 | 0 |
| Other or conflicting | 5 | 5 | 0 |
| Complete without text | 0 | 0 | 0 |
| No candidate | 0 | 2 | +2 |
| Total | 8,404 | 8,430 | +26 |

Net changes describe aggregate counts, not a proven source-correlated additions/removals/transitions ledger. Equal old/current counts do not prove identical membership. The 26 sources with multiple candidate versions and 38 sources with candidates but no recorded archive ID are overlapping traits inside current unresolved records; do not add them to the total or equate the multi-candidate 26 with the net unresolved increase of 26. Missing archive metadata does not establish missing bytes. Five availability exceptions and five other/conflicting unresolved records remain separate sets.

**Verified hashes and receipts.**
- Current recovery projection: `6f0da7b4a7181cc56f96828cf9cf73e5143488b2911fa56dfd62acbd6c981058`.
- Full current core invariants: `b3fcab239acd361183b22dd98b8a2aaa42b99817533b2e2528de3a5475e8c872`.
- Current represented-source set: `aa865cd16a5abed5f6e5f0f43f7e872387a13c524d2c7f4b4b1dd5c8ea9af0d9`.
- Current held-source set: `af68986deac3f83edfa7b19c9358f5cbcd31f15fe77ef8baaf7ad6790a77a167`.
- Four exact original receipt rows: `cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af`, unchanged on both connections. IDs remain 95838b67-b96f-4d75-a079-d1c4b72bfddb, fb31513b-df74-4e08-8a33-40f63ea306f6, 4a7de341-6c03-4233-9b9f-41fdcf43abd8 and 99bf8254-40d4-4327-8511-f834127623ef. Every field, including matched counts and creation times, matched the original preserved rows.

ACCEPTED_PROJECTION_MATCH=0 confirms that the old approved `7836ad36e47829cdf3bf34ae269d5868017cee39759ae314da6912f0945ac3a9` projection differs. Current independent stability closes the read-only snapshot-consistency gap. It does not retrospectively establish which historical identities or fields changed.

**No writes and independent empty-target readback.** Both connections verified zero plan, batch and event rows for `salus-availability-recovery-plan-20261115`. PRESERVED_RECEIPTS=4; DATABASE_WRITES=0; NEW_RECEIPTS=0; PLAN_PREPARATION=0; SOURCE_CONTENT_DOWNLOADS=0; HISTORICAL_MEMBERSHIP_RECONSTRUCTED=0; NEW_BASELINE_ADOPTED=0. No search was repeated; no source, classification, receipt, rights, hold, retry or checkpoint record was changed. There are no prepared recovery batches to process. SAL-D118 review and SAL-D119 paused-retry obligations remain in force.

**Cleanup independently accepted.** Execution status Succeeded and log-fetch exit 0 were observed at 21:05:58 UTC. At 21:05:59.6328271 UTC (15:05:59 CST), selected full app/worker identity, template and configuration matched before/after under ARM API 2025-07-01. At 21:06:19.5111386 UTC (15:06:19 CST), isolated `salcapa-cohort-drift-b48224` deletion and actual absence were verified after tag/image checks. Both cleanup markers equal 1. App/worker remain v3.223, digest `8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c`. Held v3.276 digest `550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944` was used only for isolated execution; no promotion occurred.

**Remaining gaps and next governed recovery steps.** The current count is 8,430 unresolved, not a newly validated historical 8,404. Original #1245 inner failure telemetry remains unavailable; the local PLAN_08 reproduction is still not historical proof. No Graph inventory ran in this diagnostic: the prior #1249 stable 23,747-file pair remains its separate 20:17–20:18 UTC observation, not a fresh physical boundary for these database snapshots.

1. Locate retained source-correlated historical membership and transition evidence through authorized records; preserve all versions, rights and provenance. Neither a hash nor net +125/+99/+26 can reconstruct old membership or prove an additions-only delta. Do not call the aggregate comparison a completed identity reconciliation.
2. If historical membership cannot be recovered, record that gap explicitly and seek a governed prospective-baseline decision. Preserve the four original receipts as immutable original-window evidence. They do not establish consideration coverage for a changed 23,757-source corpus; any approved new/delta consideration must be separately evidenced without replacing them.
3. Prepare a separately pinned planning candidate only after membership/scope and current search coverage are reconciled. Require a fresh stable physical inventory/current representation check, source-correlated current cohort manifest, separately linked availability exceptions, bounded append-only planning writes, receipt preservation, independent durable readback and cleanup. Obtain exact-version approval before its protected run. Do not substitute a new hash/count into #1249 and replay it.
4. Keep all batches Prepared - Not Authorized for Processing; no extraction or automatic/paused retry/hold resumption is authorized by this diagnostic. No new baseline, plan or recovery acceptance is claimed. Reader/assessment/collection and separate rollout holds remain unchanged.

The current approval and results are retained in this restricted chat and governed repository evidence. Universal chat/work-chat export/backfill and task-wide content availability remain separate documented gaps; no duplicate Library copy of repository-backed source was created.



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
