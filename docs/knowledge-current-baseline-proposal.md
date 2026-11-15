# Current recovery baseline proposal: source membership and search coverage

Status: prepared candidate. No protected run, new task search receipt, private source-level proposal, baseline approval or recovery batch has been created by this candidate.

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
