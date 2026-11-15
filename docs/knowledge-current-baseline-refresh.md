# Bounded locked refresh for the current baseline proposal

Status: approved #1259 executed once; proposal and four fresh receipts committed and independently verified. Baseline approval remains pending. Do not replay this activation.

## 15 November 2026 Central — Current source-level baseline and four fresh receipts committed and independently verified; baseline approval pending

**Outcome and exact version.** Marc approved PR #1259 exact head `9fac206439ef148b449f079065bab7d11b9d98cb` in restricted chat `01a1dccc-3c40-7c60-b6eb-f9836bd1332e`, turn `01a1e155-cce1-7f92-b344-2d8c39a780b7`, direct message `01a1e155-cdda-7be0-8d57-89e1995af8c0` and matching approval reply `01a1e155-d84d-79d1-a46d-905680bf6a70`. All five governing records at `3d32caa4fbf56d5de852e0cc1976760ff5f1cdf8` were refreshed and unchanged. All eight applicable exact-head jobs passed, including 51 PostgreSQL tests and the actual 40-field guard. Squash merge `66400ed46e8146e0429dca341950131c7ea0810d` preserved all seven approved blobs. Protected run [43769786652](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/43769786652), attempt 1, succeeded; approval job 132982895324 and task job 132982931817 succeeded. All 12 non-protected post-merge jobs passed. No prior activation was replayed.

**Prepared proposal for separate approval.** Logical proposal `salus-current-recovery-baseline-proposal-20261115`; execution phase `salus-current-recovery-baseline-refresh-20261115`. State remains **Proposed - Awaiting Baseline Approval**. Manifest SHA-256 `9a662aa94726890dfc7e4845620161ab372d81c2cc27ba8f45d84ee694840821`. See [the baseline approval summary](docs/knowledge-current-baseline-approval-20261115.md) for the precise decision, scope and retained gaps. This accepts successful proposal preparation, current membership/consideration verification and cleanup; it does not adopt the baseline or authorize recovery batches/processing.

The private proposal header, 23,757 member rows and one creation event are retained in m365_knowledge_baseline_proposals, m365_knowledge_baseline_members and m365_knowledge_baseline_events under the logical key. Every represented identity is correlated to current/root presence, all candidate versions, provenance, rights/hold metadata, category, classification hashes and four considered/matched flags. No source identities/names/paths or reviewer values were published to GitHub logs. The header binds every member hash and all original/new receipt fields.

**Stable physical and represented membership.** Complete inventories at 22:35:31, 22:36:59 and 22:39:57 UTC on 15 November 2026 (16:35:31, 16:36:59 and 16:39:57 CST) each contained 23,747 physical files, SHA-256 `0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613`. Initial pair differences were all zero and final exact equality passed. All current files were represented, missing zero in each of seven areas. Locked represented count was 23,757, with exactly ten retained representations outside the current root inventory; this is not proof of deletion or absent archive bytes.

Current legacy available count is 15,327; exact Complete/nonempty and strict string/non-whitespace text sets both contain 15,322. The 8,430 legacy-unresolved sources and five separate availability exceptions give an exact-text complement of 8,435. All values were stable between the read-only preview and locked current proposal construction.

| Unresolved category | Sources |
|---|---:|
| Governed review | 7,085 |
| Retry paused | 733 |
| Automatic retry | 512 |
| Governed hold | 93 |
| Other or conflicting | 5 |
| No candidate | 2 |
| Complete without text | 0 |
| **Total** | **8,430** |

The five other/conflicting unresolved records and five availability exceptions remain separate. Source-level category, exception and exact-text membership were checked per identity; equal aggregate counts were not used as a substitute for identity reconciliation. Current source-level membership is durably retained; the historical 8,404 identity set is still not reconstructed.

**Observed drift and bounded remedy.** The locked refresh began at 22:40:05.178175 UTC and directly observed one candidate change: reviewed_at only. Candidate additions/removals, hold changes, bulk changes and represented additions/removals were zero; no identity, name/path/owner, version/archive/destination/removal, classification, decision or category change was reported. One affected source was re-queried and its candidate search/parsed metadata refreshed; bulk/hold flags were fully refreshed. Current rights/dispositions were retained, with proposal authority false. Private source-correlated before/after row fingerprints and fixed changed-field names are bound in the proposal's locked_refresh metadata. This identifies this run's review-timestamp change; it does not establish the actor or retroactively prove #1255 changed the same field.

Source-state capture and four query families were evaluated under the approved short locks without changing source records. Atomic write phase began at 22:40:15.958464 UTC; acknowledged commit reported at 22:40:27.5586059 UTC. Actual commit window 29,915 ms, within the 60-second limit. New independent READ ONLY, REPEATABLE READ verification began at 22:40:27.641057 UTC and completed at 22:40:44.2454305 UTC (16:40:44 CST). Exact header/member/event payloads and hashes, all eight relevant receipt rows, empty original planning-target rows and the committed current core matched. LOCKED_REFRESH_VERIFIED=1, CANDIDATE_SOURCES_REFRESHED=1, FRESH_CONNECTION_VERIFIED=1 and PROPOSAL_COMPLETE=1.

**Receipts and consideration coverage.** All four original full rows matched at prechecks, locked verification and independent durable readback; canonical SHA-256 remains `cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af`. Original IDs remain 95838b67-b96f-4d75-a079-d1c4b72bfddb, fb31513b-df74-4e08-8a33-40f63ea306f6, 4a7de341-6c03-4233-9b9f-41fdcf43abd8 and 99bf8254-40d4-4327-8511-f834127623ef; every original field, matched count and creation timestamp is preserved. Their historical 23,632/15,228/8,404 counts remain historical observations.

Four fresh receipt rows committed atomically with the proposal. Each binds boundary 23,747, considered 23,757, legacy available 15,327, metadata-only/unresolved 8,430 and holds 93. All four queries considered every represented source, including all 8,430 unresolved sources; every physical file was in that set. Matched plus no-match equals 23,757 per query.

| Query | New receipt ID | Considered | Matched | Without match |
|---|---|---:|---:|---:|
| membership | 5a49b2ef-f840-418b-9c92-87839da53661 | 23,757 | 23,757 | 0 |
| coverage | 5da6b229-b1c1-4a4a-8252-d49cb234d28b | 23,757 | 23,662 | 95 |
| contrary | 47a35274-597b-4e49-8d08-7df5999dd64d | 23,757 | 12,649 | 11,108 |
| verification | 0a0d1f8e-11e3-4373-b140-a900325e8ce7 | 23,757 | 23,662 | 95 |

New query SHA-256 values, independently recomputed from approved source, are:
- membership: `85a2ac81e33e697b96b022199b9320a9cc7b4ab6a5f9bc000b0d75868b730349`.
- coverage: `040af34904511a7015b7de554d6a553469d6afd6506480366635fa22b7eab177`.
- contrary: `fbd8e89949b164dc69709d6ef213675a1aa778971d5479b5bf4212e829d356e1`.
- verification: `28f017d188b30007d688c72b6fd611abaf3e4bafa8e20ea6baef8fc1a138a948`.

New receipt timestamps and every other field were verified against the exact private header; no unobserved public timestamp is invented here. Query matches are relevance flags, not content qualification. These receipts close current represented-corpus consideration and member-correlation gaps for this captured baseline; they do not establish that all source contents were available/read, that every authorized location or historical export was exhausted, or that the old 8,404 identities were reconstructed.

**Hashes and boundary.** Current whole-core SHA-256 `58e24d39b31cad1e5d183ab25d47240bc5ccf4ec0e51dc417ba6192e0efd2652`; search-matrix SHA-256 `7742e4f6adcdc730e203a299af35dbad5ed028a100253e671b3baaddd9be4177`. Source-record writes zero; baseline accepted zero; processing authorized zero; recovery batches prepared zero; historical membership reconstructed zero. Original planning target `salus-availability-recovery-plan-20261115` still has zero plan/batch/event rows. Proposal/new-receipt writes are the authorized append-only records; do not call this run database-read-only.

**Cleanup independently accepted.** At 22:41:29 UTC, isolated execution Succeeded and log-fetch exit 0 were observed. Complete selected app/worker identity, template and configuration matched before/after under ARM API 2025-07-01 at 22:41:31.4197176 UTC (16:41:31 CST). New isolated job `salcapa-baseline-refresh-b48224` passed tag/image checks, was removed and actual absence verified at 22:41:51.0951777 UTC (16:41:51 CST). Both markers equal 1. App/worker remain v3.223 digest `8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c`; held v3.276 digest `550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944` was isolated execution only. This run made no source, rights, retry/hold or checkpoint changes and initiated no reader, assessment, release or runtime-promotion action.

**Next steps and retained gaps.** Obtain Marc's separate approval of the exact manifest above as the current metadata/consideration baseline for recovery planning, explicitly retaining the historical membership gap and source qualification/availability limits. Until then keep state Proposed. After approval, record the decision and exact artifact identity through the governing registers and prepare a separately pinned plan candidate from the captured source identities, revalidating current rights/versions and later changes. Keep the 733 paused sources and 93 held sources protected; baseline approval does not resume any of the 512 automatic retries or authorize batch processing.

Historical 8,404 membership, original #1245 inner telemetry, universal chat/work-chat export/backfill, original-byte/archive integrity, extraction recovery and human content qualification remain separate obligations. Current approval and results are captured by restricted chat and immutable source/run references; no duplicate Library copy of repository-backed code was created. Capture summary/pointers do not prove complete chat ingestion.

## Candidate design and validation history


Status: tested local candidate; no protected execution of this refresh has occurred. No baseline proposal or new receipt was committed by #1255.

## Verified problem and unchanged authority

Approved #1255 head 4354fcfe6b297270485770e5afc897ac7d1c34e3 merged as 553f7acf31f9898ccd98ea5cbef96b602a61738a and ran once as 43765713976. Three physical inventories were identical: 23,747 files, SHA-256 0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613. Current snapshot counts matched the expected 8,430-source partition, and every physical file was represented. The locked comparison stopped at SOURCE_OR_SEARCH_INPUT_DRIFT before enabling writes or attempting commit. Cleanup and full selected runtime comparison passed. Closeout #1257 records the exact phase/times and limits.

The changed table/field/source was not retained by that version. Frozen worker code permits bulk search-metadata/status changes and retry classification-JSON updates without changing physical files or category counts. This is a possible update path, not a proven cause for any particular production row. No claim is made that the observed change was harmless.

Preserve all four original full receipt rows and SHA-256 cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af. Keep original planning target salus-availability-recovery-plan-20261115 empty. Logical proposal key remains salus-current-recovery-baseline-proposal-20261115; the failed run created neither its proposal nor its four new receipts. This is a new execution phase, salus-current-recovery-baseline-refresh-20261115, with a new activation and isolated job. The previous activation is not replayed or modified.

## Bounded remedy for proposal preparation only

The original candidate required an earlier full database/search snapshot to remain unchanged through a final Graph inventory. The replacement retains physical inventory proof, source/version/rights controls, the named cohort and append-only writes, while evaluating permitted changed metadata from the current locked state before preparing the proposal.

1. Obtain the stable full-root physical inventory, complete represented membership and a READ ONLY, REPEATABLE READ preview, as before. Compute candidate, bulk and hold search flags separately using the same deployed tokenization, union, lower()/LIKE OR semantics and four exact task queries. Their per-source OR must equal the original full search. Each represented source has four considered flags.
2. Obtain the final physical inventory outside the commit locks and require exact equality. Acquire the existing advisory lock and NOWAIT SHARE locks. The total lock/write budget remains 60 seconds, statement budget at most 30 seconds, lock timeout two seconds.
3. Read current complete core/search-input fingerprints and calculate source-correlated drift. Public telemetry records only fixed table/field names and counts. The private proposal retains source keys, changed-field names and before/after row hashes plus preview/current whole-core hashes. Never print source IDs, names, paths, reviewer values, raw text or provider errors.
4. Reject additions/removals or represented-identity changes. Reject candidate/source identity, name/path/owner, version/hash/archive/destination/removal provenance changes; reject hold identity/version/area changes and bulk identity/parent/version/size changes.
5. Only these existing metadata changes may be evaluated afresh for a proposal: candidate classification hash, status/decision/reviewer/rationale/time/target-folder fields; hold reason, research/teaching/citation dispositions and reviewer fields; bulk status, reason and metadata hash. This does not authorize any source update or confer rights, qualification, approval or processing.
6. At most 100 affected candidate sources may be refreshed. Re-query their complete candidate versions and parsed scalar evidence under the lock; recompute their candidate search flags. Candidate flags may be reused only for sources whose entire candidate core/search inputs were proven unchanged. Bulk and hold flags are always fully recomputed from the locked current state; these are metadata queries without whole-corpus classification parsing.
7. Rebuild the proposal from current evidence and match flags. Require the same represented identities, every source's category/availability-exception/exact-text membership, and the exact 8,430 partition. Equal category totals cannot hide source swaps. Changed identity/version, excessive candidate refresh, changed per-source cohort, coverage gaps or any deadline failure stops before writes.
8. Append the same three proposal tables and four fresh consideration receipts atomically. Preserve all original receipts and empty original planning target. State remains Proposed - Awaiting Baseline Approval; baseline accepted, processing authority and customer release remain false. No recovery batches are prepared.
9. Independently read back the exact committed header, every member, event, all original/new receipt rows and the committed current core. Post-commit source drift gets table/field counters and fails the current-state verification; it must not be treated as zero writes when COMMIT_ACKNOWLEDGED=1. No ambiguous or partial result may be replayed.

This refresh is only a way to capture a coherent current **proposal** before human approval. It does not refresh a processing plan or waive current source rights. Candidate source content is not downloaded; SQL projects only metadata, hashes and text-presence/match booleans. Holds, paused retries and extraction checkpoints are never changed. All allowed rights/decision values are retained as observed metadata, with proposal-level authority false.

The prior quadratic repeated available-minus-exact set calculation in member construction is replaced by one precomputed set. This avoids extra time under the lock without changing membership semantics.

## Protected bindings and validation

The new activation is deploy/azure/activations/knowledge-baseline-refresh-20261115.json. The workflow triggers protected push execution only when this new activation changes. The old knowledge-baseline-proposal-20261115.json remains unchanged. Exact binding covers all 40 activation fields, the new script SHA-256 ae518470df0b531b7f8fb52f77192e696acdce54def130dbf15eb71c7c34b57b and unchanged support SHA-256 2bfaf1b5c16c6a66f77bd69c61dec7a36afc6cefe3c9b7f67795972586d0ee49. CI also checks phase/logical-key/100-source constants and the actual encoded payload size.

Protected environment salcapa-dev-approval; attempt 1 only; same diagnostic concurrency group; no manual dispatch or replica retries. New isolated job salcapa-baseline-refresh-b48224 is tag/image checked and removed with actual absence verification. Execution remains held v3.276 digest 550cd447b280c83594a70d541d757c91ee3b3ff4833ce9a1713279e6cdc6d944; app/worker stay v3.223 digest 8f5823ef53d08eaa319f8073b00b6d817ab3db5e07b8f55c0dffb72868cd580c. Maximum 900 seconds, 0.5 CPU/1 GiB. Complete selected runtime identity/template/configuration comparison uses ARM API 2025-07-01.

Local: 25 tests passed; 26 PostgreSQL-only skipped. CI must pass all 51 tests with PostgreSQL 16, actual 40-field guard/replay/two-script tampering checks, shell syntax, Bicep compilation, constant and bootstrap-size checks, and repository gates. Tests retain the original strict guard reproduction; prove family recombination and subset/full projection equivalence, fresh bulk/candidate/hold matching, rights retention without authority, exact independent current readback, rejection of identity/version/over-limit/per-source membership changes, atomic rollback, receipt preservation, deadline and ambiguous commit handling.

## Required next gates and retained gaps

Obtain approval of the new exact tested head before merge and one protected refresh run. Check field-level drift and actual scope, unchanged source identities/versions, all four originals, four new receipts, exact private member/manifest/event records, fresh current-core verification, commit acknowledgement, runtime and isolated-job absence. Only a fully verified proposal may be presented for separate baseline approval. No baseline or processing approval is granted by this code change.

Historical 8,404 membership reconstruction, original #1245 inner telemetry and universal chat/export/backfill remain gaps. The old four receipts do not prove current corpus consideration. Fresh queries and source-level membership must be durably coupled in the successful new run, never inferred from counts or an attempted search. The original failure record remains authoritative history.
