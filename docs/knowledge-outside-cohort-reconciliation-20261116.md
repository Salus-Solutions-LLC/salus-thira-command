# Governed two-record outside-cohort reconciliation

Controlled candidate, 16 November 2026. This diagnostic is read-only and requires separate exact-version human approval before merge and one isolated execution. It does not adopt a baseline, change records, create receipts, prepare recovery batches, access source bytes, qualify methods or resume retries/holds.

## Verified starting point and actual gap

Approved #1285 merged as `7f78e7f7739a8a40fc5d319029b27334db908ead`; run 43941369222 succeeded. Administrative #1288 merged as `cd8ca1cfceba5c9e2b3f6f2d5e1c4b871e879997`, with full handoff/artifact/index readback. Three complete inventories matched at 23,757 physical files, digest `25a11e7d0956a2178d6033a3687e1a1a185873d7e5ade9550a60dae09b40b8ab`. Current representation was 23,767 with 8,432 unresolved. The approved recovery roster remains 8,430.

Ten current physical identities were added outside the original baseline; all ten were represented. The earlier report did not bind their current categories, so the two additional unresolved identities must not be assumed to be two of the ten. The historical intermediate 23,748-file snapshot remains unreconstructed. No count identifies a source or grants recovery authority.

## Source binding and bounded independent verification

Reconstruct the complete original baseline from its stored hash-bound members and verify all twenty full receipt rows and input manifests. Use the same metadata-only queries, database-enforced read-only repeatable-read transactions and complete three-observation inventory stability check. Derive the current unresolved identity set minus the original unresolved roster, rather than selecting the first two records or relying on count differences.

For exactly two records, emit source-identity hashes, current category, baseline category and physical membership, relation to current physical additions, candidate count, current inventory-row digest, critical source/version/rights-metadata digest, candidate-version digest, provenance digest, hold digest, paused/held flags and four per-source query match flags. Do not emit names, paths, owners, raw IDs, raw rights text or source contents. Digests bind recorded metadata; they do not prove content quality, source rights or human qualification.

Relations distinguish baseline members that were previously available, added physical identities outside the baseline, and represented identities outside the baseline that lack a current physical row. Independently reconstruct the same two full bindings through a fresh connection. Require exact equality, unchanged approved critical bindings, no represented membership changes, and no outside-cohort critical metadata changes between connections. A same-count identity swap cannot pass.

The fixed boundary is 23,757 physical / 23,767 represented / 8,432 unresolved, the previously verified complete inventory digest and ten-source difference-collection digest. Preserve the exact twenty-receipt digest, all 733 paused and 93 held source memberships and the protected checkpoint digest. Any drift stops with a bounded failure and cleanup; it never refreshes or silently expands scope. The new operation's own receipt target must remain empty, along with prior failed targets.

## Runtime, action and cleanup boundaries

Preserve the successful #1285 workflow, activation and payload unchanged. Add a separate activation/workflow/job namespace `salcapa-outside-b48224` with task tag `salus-outside-cohort-reconciliation-20261116`. Reuse the tested GET-only bounded transport: five requests per read, 120-second read budget, 30-second request timeout, 8 MiB bound, Retry-After compliance and no authorization bypass. Submit once and start once; never automatically repeat either after an ambiguous acknowledgement. Always attempt terminal collection before cleanup.

Keep the execution-only v3.276 image and v3.223 app/worker runtime digests pinned. Keep 0.5 CPU / 1 GiB, 900-second execution, zero container retries, 786,432 KiB memory guard, bounded payload/output, page size 100 and statement timeout 120 seconds. Retain complete terminal evidence, independent result validation, full selected app/worker identity/template/configuration equality and all-page namespace absence after removing only the correctly tagged job. Preserve the personal SalusScan2 email opt-out, Compass pause and disabled reader.

## Approval and next steps

Candidate tests cover real SQLite/PostgreSQL read-only enforcement, full receipt preservation, two-source classification/provenance binding, missing physical representation, previously available membership, identity/version swaps, pause/hold drift, output privacy and the actual activation/bootstrap/shell controls. Required PostgreSQL, guard and Bicep checks must pass before requesting approval.

After the approved run, record the actual two hashed bindings and categories, their relation to the ten additions or other baseline members, independent readback and cleanup. Only then prepare a justified baseline-scope proposal or further bounded continuation for explicit approval. Do not expand the original 200 batches or execute preflight/recovery. Content, rights, historical membership, faithful chat capture and global assurance gaps remain open.

Design references: [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html) explains snapshot boundaries; [Microsoft Graph driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0) requires complete paginated enumeration. These support the diagnostic controls, not historical identity attribution or exhaustive content review.
