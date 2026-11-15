# Current recovery baseline proposal: source membership and search coverage

Status: approved #1255 merged and executed once; stopped before writes on source/search-input drift. No durable baseline or new receipts were created. Cleanup passed.

## 15 November 2026 Central — Approved current-baseline run stopped on source/search-input drift before writes; receipts preserved at locked precheck, cleanup verified

Marc approved PR #1255 exact head `4354fcfe6b297270485770e5afc897ac7d1c34e3` in restricted chat `01a1dccc-3c40-7c60-b6eb-f9836bd1332e`, turn `01a1e12e-1495-7383-8f9a-3a6be4403b9f`, direct message `01a1e12e-15ab-7a73-92cf-be364a73ca24` and matching approval reply `01a1e12e-88b5-7f63-8218-f4ad3501a10c`. Refreshed all five governing records at `aaf79e7e04d86e6ad741161fdefbf0098ed16a23`; unchanged from accepted preparation. All eight applicable exact-head jobs passed, including 35 PostgreSQL tests and the actual 37-field guard. Squash merge `553f7acf31f9898ccd98ea5cbef96b602a61738a` preserved all seven approved source blobs. No prior activation was replayed.

Protected run [43765713976](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/43765713976), attempt 1, executed that merge. Approval job 132970212503 succeeded; task job 132970252744 failed its main step and passed cleanup. All 12 non-protected post-merge jobs passed. **No durable baseline proposal was prepared; no new receipt or recovery batch was created; baseline adoption remains unapproved.**

**Observed current metadata and inventory.** Three complete physical inventories at 21:51:37, 21:53:08 and 21:56:20 UTC on 15 November 2026 (15:51:37, 15:53:08 and 15:56:20 CST) each contained 23,747 files with SHA-256 `0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613`. The initial pair had zero differences in every compared field; final inventory equality passed. In the READ ONLY, REPEATABLE READ metadata/search snapshot begun 21:53:08 UTC, every current file was represented and missing counts were zero in all seven areas. Observed represented 23,757, legacy available 15,327, unresolved 8,430, exact/strict text 15,322 and availability exceptions five. The disjoint unresolved partition remained review 7,085; paused 733; automatic retry 512; held 93; other/conflicting five; Complete without text zero; no candidate two. These are snapshot-window observations, not final current-state or historical identity reconciliation.

**Precise current failure and write boundary.** The job reached bounded_atomic_proposal_and_receipts at 21:56:20.178019 UTC after all Graph reads. Under the advisory/NOWAIT source and receipt locks it reverified the exact original receipt rows, zero original planning-target plan/batch/event rows, and no existing proposal/new-task receipts. It then compared the current full source/search-input core with the earlier read-only snapshot. At 21:56:27.2795815 UTC (15:56:27 CST), SOURCE_OR_SEARCH_INPUT_DRIFT stopped the run. SQLSTATE UNAVAILABLE; COMMIT_ATTEMPTED=0 and COMMIT_ACKNOWLEDGED=0. The source code stops and rolls back at that comparison before enabling proposal writes, creating any proposal table, inserting any new receipt/member/event, or attempting commit.

All four original full receipt rows therefore matched at the locked precheck, including canonical digest `cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af`; the job never updates them. Original target counts were zero at 21:49:58, 21:53:08 and 21:56:20 UTC. No final independent durable readback was reached, so do not label the locked precheck as post-run independent verification. No new receipt ID, member-manifest SHA or private proposal was emitted or durably committed. The four fresh queries were evaluated against the earlier consistent snapshot, but their receipts/manifest were not persisted and their results cannot be claimed as reconciled current coverage after detected drift.

The actual changed table, source identities, fields and values were not retained in this version's aggregate failure telemetry. Physical equality and unchanged counts do not prove the change was harmless. Inspected frozen salcapa_bulk_delta.py and salcapa_bulk_extraction_retry.py: existing workers can update bulk status/search metadata and candidate classification JSON while physical metadata and category totals remain unchanged. That is a documented possible update path, **not proof of which production field changed**. Do not attribute the observed stop to scheduler-only data or bypass the guard from counts alone.

**Cleanup independently accepted.** At 21:57:05 UTC, execution Failed and log-fetch exit 0 were observed. Full selected app/worker identity, template and configuration matched before/after under ARM API 2025-07-01 at 21:57:07.2480059 UTC (15:57:07 CST). Isolated job `salcapa-baseline-proposal-b48224` was tag/image checked, removed and actual absence verified at 21:57:26.7712600 UTC (15:57:26 CST). Both markers equal 1. Accepted app/worker remain v3.223 digest `8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c`; held v3.276 digest `550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944` was isolated execution only. No source, rights, retry, hold, checkpoint or application changes were made by this task.

**Next governed work.** Prepare and test a separately protected candidate that records table/field-level aggregate drift and private source-correlated before/after fingerprints. For proposal preparation only, consider a bounded current-metadata/search refresh under the short commit lock, reusing only proven unchanged search inputs, re-querying changed inputs and retaining all rights/provenance. Identity/version/membership changes, excess refresh scope, an altered 8,430 partition, changed original receipts or ambiguous evidence must stop safely. Preserve the four originals, atomically couple any future four fresh receipts with exact private member rows, and verify durable readback/cleanup. Do not replay #1255, silently substitute hashes, relax processing/hold controls, or claim baseline acceptance. A changed executable/activation requires new exact-version approval. Current-baseline approval remains a later separate decision after an actual proposal is verified.

Historical 8,404 membership reconstruction, original #1245 inner telemetry and universal chat/work-chat export/backfill remain separate gaps. This failed run did not close them. Current task authorization/results are retained through restricted chat and immutable governed source/run references; no duplicate Library copy of repository-backed code was created.



## Objective and authority

Prepare a current source-correlated proposal for the 8,430 unresolved records measured by accepted read-only run 43761349512, while preserving the four original receipts. The proposal must remain **Proposed - Awaiting Baseline Approval**. Executing this candidate and accepting the resulting baseline are separate approvals. Do not resume retries or holds, prepare processing batches or promote an image.

Inspected development/salcapa-platform at be3880d09274e4eb68bf8afec2d3bb26c866c7f7: SALUS_PROGRAM_CHARTER.md, SALUS_DECISION_REGISTER.md, CURRENT_HANDOFF.md, APPROVED_ARTIFACTS.md and SALUS_CHAT_STARTUP_PROTOCOL.md. SAL-D125, SAL-D133 and SAL-D134 govern consideration, search and capture; SAL-D118 and SAL-D119 retain review and paused-retry controls; SAL-D135 governs shared document appearance without changing this execution scope.

Accepted application/worker remain v3.223. #1252 head 1560eaf93e4755925b597790ca5e132f50f16cd3 merged as 640d54cf71d053e0731ef3990eb4ab16dec3eac6. Its two independent read-only snapshots agreed on 23,757 represented sources, 15,327 legacy-available, 15,322 exact/strict text, 8,430 unresolved and five separate availability exceptions. Diagnostic closeout #1254 merged as be3880d09274e4eb68bf8afec2d3bb26c866c7f7; zero original-target plan/batch/event rows, unchanged runtime and isolated-job absence were verified. No recovery baseline was adopted.

Expected unresolved partition: governed review 7,085; retry paused 733; automatic retry 512; governed hold 93; other/conflicting five; Complete without text zero; no candidate two. These counts bind the named scope. Initial represented/available totals may grow; this is a prospective current proposal, not a reconstruction of the earlier identity set. Any unresolved partition or availability-exception count drift stops before writes and emits observed aggregate counts. Do not silently enlarge the authorized 8,430-record scope.

## Historical evidence and limits

The original four receipt IDs are 95838b67-b96f-4d75-a079-d1c4b72bfddb, fb31513b-df74-4e08-8a33-40f63ea306f6, 4a7de341-6c03-4233-9b9f-41fdcf43abd8 and 99bf8254-40d4-4327-8511-f834127623ef. Every field must retain canonical sorted-row SHA-256 cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af. Their original-window counts remain represented 23,632, legacy available 15,228, unresolved 8,404 and holds 93.

The accepted original recovery projection was 7836ad36e47829cdf3bf34ae269d5868017cee39759ae314da6912f0945ac3a9. #1252 measured current projection 6f0da7b4a7181cc56f96828cf9cf73e5143488b2911fa56dfd62acbd6c981058. Net +125 represented, +99 available and +26 unresolved are aggregate changes. They do not prove additions-only changes, identify historical members or establish the same membership in categories with equal totals.

Inspected original census/search/planning code and retained task evidence. The earlier census paths emitted counts/hashes and consideration receipts; the original planning path never committed its source-correlated manifest. Exact-key SharePoint/OneDrive, email and Teams searches located no retained manifest in the returned results. Those are bounded indexed searches, not proof none exists anywhere. The historical exact-membership gap therefore remains explicit. Original #1245 inner failure telemetry also remains unavailable; the tested PLAN_08 defect is not a proven historical production cause.

This candidate establishes durable **current** source-level membership and current consideration coverage, with the historical gap recorded in the proposal. Acceptance must explicitly acknowledge that gap or first supply retained historical evidence. It does not claim to reconstruct the old 8,404.

## Source-level current reconciliation

1. Require exact original receipt rows and zero original-target plan/batch/event rows. Reject an existing proposal or new-task receipts; never overwrite or blindly replay.
2. Traverse the complete authorized intake-root metadata boundary, including all seven areas. Require two consecutive identical inventories within three initial observations; require at least 23,747 physical files. No file-content endpoint is used.
3. In one READ ONLY, REPEATABLE READ snapshot, require every physical source to be represented. Bind the full represented union, every candidate version, governed-hold rights/dispositions, bulk provenance and every search input to the authorized drive. Cross-drive or missing membership fails closed.
4. Record one private member row for every represented source, including represented sources outside the current physical inventory. Bind each unresolved source once to a disjoint category; keep all versions and retain two no-candidate sources explicitly. Bind the five availability exceptions separately from the five other/conflicting unresolved sources.
5. Each member records source identity/drive, current inventory metadata or explicit absence, candidate/version and provenance fields, classification hashes, holds, bulk provenance, per-query considered/matched flags, and no processing/content-qualification authority. Scheduling-only attempts, lease and checkpoint movement are not source/rights approval and are not included in this membership proposal.
6. Obtain a final physical inventory before write locks and require exact equality with the stable one. Total inventory observations are bounded at four. All Graph calls finish before the commit lock window.

Full source-correlated members remain in the existing authorized Salus database, not GitHub logs or a new enterprise Library copy. Logs expose only fixed codes, counts, query/receipt IDs and whole-proposal hashes. Source names, paths, item IDs, reviewer/owner values, raw text and provider errors are not printed. No source bytes or archive bytes are downloaded or verified; absent archive metadata remains a metadata limitation.

## Fresh coverage without replacing the four receipts

New logical operation: salus-current-recovery-baseline-proposal-20261115. Original logical planning target remains salus-availability-recovery-plan-20261115 and remains empty. Four new task-specific queries are:

| Label | Exact query |
|---|---|
| membership | recovery baseline source membership represented current historical archive version provenance |
| coverage | knowledge corpus consideration query content metadata unavailable supportive qualifying |
| contrary | hold restriction rights conflict unsafe contrary retry paused failure missing |
| verification | baseline proposal receipt audit independent verification stability cleanup approval |

The deployed service's tokenization, represented union, string concatenation, database lower()/LIKE OR semantics and availability predicate are retained. Materialized search inputs are lowered once per row; four query flags are aggregated in one SQL scan. SQL returns only source IDs and boolean match flags, with no excerpts or extracted text transfer. Tests compare all query matched/considered/available counts to the unchanged deployed consider() implementation, including null, mixed-case and Removed bulk rows still represented by candidates. The frozen release and current service source match Git blob 5d51b9aca297014c739c02e56326f2e0e45c00e4.

Every represented source, including every unresolved source, receives four considered flags; match flags are separate. Counts reconcile matched + no-match = represented, with physical subset membership proven separately. New receipt rows are bound to that exact private member manifest and query hashes. Legacy availability remains separate from exact/strict text and does not confer qualification. The task does not read every source's content or repair the legacy availability predicate.

## Atomic proposal and receipt commit

A separate short transaction takes the existing advisory lock and NOWAIT SHARE locks on candidates, governed holds, bulk items and original/new receipt storage. The transaction has a checked 60-second total budget and each SQL statement gets the remaining time capped at 30 seconds; lock timeout is two seconds. Existing source writers cause a safe stop. Queries hash classification/search metadata without JSON parsing or raw text transfer in this lock window. Every source/rights/search input, including Removed bulk rows that still participate in search, must equal the read-only snapshot.

Only these three new append-only proposal tables and four new consideration receipt inserts are allowed:

- m365_knowledge_baseline_proposals: proposal state, manifest hash and header.
- m365_knowledge_baseline_members: unique operation/source key, category, member hash and private correlated payload.
- m365_knowledge_baseline_events: one proposal-created event, with approval and processing false.

The query facade denies source/receipt UPDATE/DELETE, mutating CTEs, multi-statements, arbitrary schema changes and processing writes. Three exact CREATE TABLE IF NOT EXISTS definitions are permitted only for these proposal tables. Original receipt table/schema already exists and is not changed. Member inserts use bounded groups of 100; exact payload/hash/state and all receipt rows are read back before commit. The four new receipts and all proposal records commit together or roll back together. This avoids leaving new receipts without their member manifest.

COMMIT_ATTEMPTED and COMMIT_ACKNOWLEDGED are separate telemetry. Loss of acknowledgement requires governed readback before any further action; never infer zero writes or replay the operation. A fresh independent READ ONLY, REPEATABLE READ connection verifies the exact header, every member, all new receipts, four unchanged original receipts, original planning-target emptiness, event and unchanged current source/rights/search inputs before PROPOSAL_COMPLETE=1.

These SQL controls follow [PostgreSQL 16 transaction rules](https://www.postgresql.org/docs/16/sql-set-transaction.html), [snapshot isolation](https://www.postgresql.org/docs/16/transaction-iso.html) and [explicit locking](https://www.postgresql.org/docs/16/explicit-locking.html). Provider documentation is supporting technical evidence; real PostgreSQL CI must validate the implementation.

## Protected execution and cleanup

Merge-triggered activation only, protected salcapa-dev-approval environment, attempt 1 only, no manual dispatch or automatic retry; same salcapa-knowledge-diagnostic concurrency group. Isolated job salcapa-baseline-proposal-b48224 uses held v3.276 image digest 550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944 from frozen release/v3.276 / 7b79b2845aaa6e2bf738e0c115c10b73e4c97dd3. Accepted app/worker digest remains 8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c. One isolated replica, retry zero, 900 seconds maximum, 0.5 CPU/1 GiB. No application/worker template, image, permissions or access grant is changed.

Exact pre-Azure binding covers all 37 activation fields and both script byte hashes. Support module SHA-256 remains 2bfaf1b5c16c6a66f77bd69c61dec7a36afc6cefe3c9b7f67795972586d0ee49. Complete selected identity/template/configuration of application and worker are compared before/after using ARM API 2025-07-01. Always-run cleanup checks isolated-job tag/image, deletes only that job and verifies actual absence. The collector stays at 300 lines and publishes execution/log-fetch status before asserting success. Raw provider errors remain private.

No source processing, retries/holds, recovery planning batches, baseline adoption, customer release, Protected Member access, application promotion or previous activation replay is authorized by this candidate.

## Validation and next gates

Local: 17 SQLite tests passed; 18 dedicated PostgreSQL tests skipped locally. CI must run all 35 tests with PostgreSQL 16, actual activation-guard drift/replay/two-script tampering checks, shell syntax and Bicep compilation, plus repository checks. Fixtures cover exact membership/versions, no-candidate and historical sources, all query semantic comparisons, source/search/rights drift, atomic rollback and repeat guards, exact durable readback, original receipt preservation, chunk boundaries, SQL mutation denial, deadline and ambiguous commit. A real PostgreSQL source writer must reject NOWAIT locking before new receipts.

After candidate checks pass, obtain exact-head approval for merge and **proposal preparation only**. Run once, verify all original and new receipts, full member/manifest readback, source stability, runtime and job absence, and record exact observed IDs/counts/hashes. Only then present the resulting private baseline proposal and its historical/coverage gaps for separate approval. If approved, a later separately pinned recovery-plan candidate must revalidate current rights, versions, membership, coverage and pause/hold controls against the accepted member manifest. Baseline approval is not processing authority.
