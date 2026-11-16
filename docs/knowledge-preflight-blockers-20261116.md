# Governed preflight blocker diagnosis and bounded proposals

Controlled candidate, 16 November 2026. Operation: `salus-preflight-blocker-diagnostic-20261116`. Preparation is separate from method approval, preflight execution, recovery processing and retry/hold changes.

The prior verified run reviewed 200 remediation proposals covering 8,430 sources and selected zero sources. This candidate measures why, without treating that zero as proof of any particular cause. It preserves all 20 receipt rows and all approved baseline, plan, remediation and review records. Runtime remains v3.223; v3.276 is used only for the isolated diagnostic. The personal SalusScan2 email opt-out remains in effect.

## Inputs and authority

The activation pins the prior review manifest `48b56aa85a3098946d9c75042b64c481941a6d8c290e2ed3a42eefeb41ac8638`, verified run 43913493719, all prior input manifests, eight source hashes, five governing rows and the five-module payload checksum. The preserved baseline covers 23,757 represented identities; the approved unresolved scope is 8,430 sources in 200 batches. Historical 8,404-record reconstruction, full original-content review, archive authenticity, source rights and complete chat capture remain unresolved.

Exact-version approval is required before merging this new protected implementation and its activation. The workflow accepts only the governed branch push and attempt 1; it rejects altered activation fields, sources, governing rows and payload before Azure login. No manual dispatch, replay or automatic rerun is permitted. SAL-D140 routine OSINT-list auto-merge authority does not apply to this software or these database writes.

## Diagnosis

For each approved source, revalidate baseline/current identity and critical metadata, all candidate versions, saved remediation and review bindings, original first-blocker disposition and immutable input hashes. Regenerate current remediation semantics and reject rights, version, cohort or identity drift. Three stable inventory observations precede preparation; another observation must match before the transaction. The four task searches consider the entire current represented boundary, including out-of-scope unresolved identities, which remain considered but unselected.

Retain two different measurements: the exclusive historical first-blocker counts, which must reconcile to the prior review and total 8,430, and all applicable blocker counts, which overlap and must never be summed as unique sources. Emit fixed aggregate counts, including the automatic-retry subset, while storing source-level evidence privately. Diagnose category, method and safety review, current membership, version count/match, archive item metadata, size, version-specific method, absent or invalid SHA-256, absent archive eTag, and current size/eTag conflict independently. Rights and human qualification remain execution prerequisites; do not claim the old eligibility function checked them when it did not.

The old first-blocker function and eligibility policy remain unchanged. Reproducing zero under that policy does not authorize relaxing it. Invalid hashes and every hard identity/version/safety/size/hold/review gate remain deferred.

## Bounded proposals

At most two existing automatic-retry batches can supply up to five sources each, selected deterministically. No source with a hard blocker may enter a proposal. Missing integrity metadata can support only the following proposed methods, all marked unapproved:

| Observed metadata gap | Proposed method | Required approval and limitation |
|---|---|---|
| Missing archive eTag, with or without missing SHA-256 | Metadata identity reconciliation | Separately approve rights, exact identities, implementation and execution. Metadata requests only; a new eTag does not prove historical lineage. |
| Missing SHA-256 with all other gates satisfied | Initial current-pair hash establishment | Separately approve a new method and bounded byte-read implementation before any source access. Equality measured now cannot establish historical authenticity or replace missing historical evidence. |

No method is adopted by proposal preparation. Every proposal retains exact source/candidate/version bindings and `method_approved=false`, `source_rights_qualified=false`, `historical_integrity_proven=false` and execution/processing/retry/hold authority false. Source checkpoints are recorded, never changed. Zero suitable proposals is a valid measured result and must be reported with blocker evidence.

Future proposal limits remain two batches, five sources each, ten sources total; 10 MiB per stream, two streams per source, 200 MiB total, 300 seconds per batch and 600 seconds total, zero retries, zero paid external API calls and zero persistent source-content bytes. Metadata proposals add at most two requests per source, 20 total, 128 KiB per response and 2.5 MiB total. These are proposed limits, not authority to execute requests or byte reads in this run.

## Atomic preparation, verification and cleanup

Only four new append-only diagnostic/proposal tables and four fresh search receipt rows can be written. Before writes, verify all 20 preserved receipts and all input events and hashes, require an empty target, take the shared advisory lock and NOWAIT source/input table locks, and recheck source/search state under the lock. Use READ COMMITTED for the writing transaction so lock acquisition cannot pin an earlier repeatable-read snapshot. Allow only bounded refresh of benign metadata, with at most 100 candidate sources; source identity, version, rights and approved cohort changes fail closed.

The transaction has a 60-second budget, two-second lock timeout and statement timeout capped at the remaining budget and 30 seconds. Recompute diagnostic summaries and validate every proposal binding before writes; atomically save the diagnostic header, 200 diagnostic batches, zero to two proposals, one event and four current-task receipts. Independently verify all output bytes/hashes and the 20 preserved receipts before commit and on a fresh connection after commit. Compare current source state after commit. A missing commit acknowledgement is ambiguous completion and must be reconciled read-only; never replay preparation.

Retain the existing 0.5 CPU/1 GiB, 900-second job, zero retries, 786,432 KiB memory guard, 24 MiB output bound, 262,144-byte decompressed payload bound and single-argument bound. Cleanup always compares full selected ARM identity/template/configuration for the app and worker, deletes only the task-tagged isolated job, and independently lists the namespace to prove absence. Record terminal execution status and sanitized exit/OOM evidence before deletion. Cleanup alone does not establish successful diagnostic preparation.

## Evidence and next approval steps

The live result must report the exact operation manifest, run and implementation version; exclusive and overlapping blocker counts; proposal/source/method counts and exact private selection hashes; 20 unchanged old receipts plus four new full receipt rows; source/input/parent/baseline write counts of zero; independent readback; app/worker equality; isolated-job absence; and any remaining uncertainty. Update the handoff and artifact/authority records through their applicable gates. Preserve all prior handoff history.

After diagnostic preparation, Marc reviews the exact manifest and any bounded proposals. A competent owner must separately approve the method, source rights, implementation, resource/cost bounds and exact source selection. A further exact-version execution approval is required before metadata preflight requests, byte reads or any recovery action. Paused retries and holds remain preserved throughout.

## Primary references and claim limits

- [Microsoft Graph hashes](https://learn.microsoft.com/en-us/graph/api/resources/hashes?view=graph-rest-1.0): `sha256Hash` is unsupported. Metadata lookup cannot be represented as retrieving trustworthy historical SHA-256; SHA-1/QuickXor are not substitutes.
- [Microsoft Graph driveItem metadata](https://learn.microsoft.com/en-us/graph/api/driveitem-get?view=graph-rest-1.0): bounded identity/eTag metadata can support reconciliation, subject to rights and exact version bindings.
- [Microsoft Graph content download](https://learn.microsoft.com/en-us/graph/api/driveitem-get-content?view=graph-rest-1.0): future byte methods must account for redirects and independently enforce stream limits. This run performs no content downloads.
- [PostgreSQL 16 explicit locks](https://www.postgresql.org/docs/16/sql-lock.html): shared table locks block conflicting writers; NOWAIT fails promptly. Snapshot ordering and isolation require explicit handling.
- [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html): layered validation and independent resource limits inform later implementation review; no source qualification is inferred.

These references support specific design decisions. They do not establish exhaustive internet review, source-content qualification, historical authenticity or complete Charter compliance.
