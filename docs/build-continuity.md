---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 14:21 CDT
current_frozen_release: v3.109
current_frozen_commit: 361a38300faddd7e9a93153c0629739acef870a0
active_development_branch: development/salcapa-platform
active_roadmap_issue: 124
active_increment: issue_124_candidate_image_live_acceptance_preflight
last_completed_release: v3.109
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: live_v336_database_migration_candidate_image_entra_reporting_recovery_and_rollback_acceptance_missing
next_authorized_increment: issue_124_candidate_image_live_acceptance_preflight
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. It is deliberately small so a new work session can establish verified state without reconstructing the product from conversation history.

## Source precedence

When records disagree, use this order:

1. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.
2. This continuity record, after checking it against those GitHub records.
3. Approved architecture and doctrine records referenced by the active roadmap issue.
4. Conversation history only as supporting design context.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Verified checkpoint

- Current frozen release: **v3.109** at [`361a38300faddd7e9a93153c0629739acef870a0`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/361a38300faddd7e9a93153c0629739acef870a0) on `release/v3.109`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), governed maintenance and promotion of the Azure development demonstration with three deterministic fictional Protected Member environments. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) remains open and its approved scanned-PDF implementation is preserved as the next product-capability increment after the materially lagging demonstration is made promotion-ready.
- Last completed increment: v3.109 adds native local JPEG/PNG printed, handwritten, mixed, and targeted-region recognition; immutable job/profile/artifact/transform/source-region lineage; explicit alternate and uncertain readings; independent review and append-only correction; manual transcription; interface guidance; and portable backup/recovery hooks. It adds no scanned-PDF rendering, external-provider transmission, authorship conclusion, identity conclusion, finding, or disclosure authority.
- Last controlled validation: [PR #249](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/249), on which all 17 required workflow families passed on exact frozen v3.109 commit [`361a38300faddd7e9a93153c0629739acef870a0`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/361a38300faddd7e9a93153c0629739acef870a0). The pull request was closed without merge.
- Current candidate: none. Frozen v3.109 and every earlier frozen release remain immutable.
- Last completed development increment: the accepted-v3.36 migration and recovery rehearsal checks out exact frozen commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b), verifies pinned source identities, migrates its governed demonstration baseline into the current runtime without changing accepted records, verifies immutable report-snapshot integrity, adds the three fictional environments, and exercises tenant-scoped restore and rollback without changing the other tenants. SQLite, PostgreSQL 16, and the production container passed. [Validation PR #260](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/260) passed all 19 workflow families on exact head [`98edaa7b7731d64c67761d02b0de7286fb905cbe`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/98edaa7b7731d64c67761d02b0de7286fb905cbe) and was closed without merge. No Azure resource was contacted or changed by the rehearsal.
- Genuine blocker to demonstration promotion: deterministic fixtures, bounded cross-functional records, repository role/tenant preflight, and an exact-source migration/recovery rehearsal are verified. Migration of a copy of the live accepted v3.36 database, Microsoft Entra identity and tenant-isolation acceptance, immutable candidate-image acceptance, live reporting, Azure recovery, and Azure rollback remain unverified. This does not block safe repository work; the accepted Azure deployment remains unchanged.
- Demonstration checkpoint: the [governed demonstration continuity record](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/demo-deployment-continuity.md) verifies that the most recent successful application-deployment workflow promoted v3.36 at `63d513605f908d3308bb5dd1bbdbf1061878452b` on 06 September 2026 at 13:18 CDT. Its acceptance covered live runtime readiness and identity/dependency configuration, not the full three-member Issue #124 journey.
- Last accepted architecture: the [scanned-PDF page-rendering design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-scanned-pdf-page-rendering-design.md) extends the approved handwriting and expanded-OCR design with embedded-text-first inspection, page-specific authority and purpose, local hash-pinned rendering, exact PDF-point and rendered-pixel transforms, ephemeral page bytes, independent source comparison, and low-cost graceful degradation. Exact page coordinates and authorized geographic coordinates remain preserved and usable; only unintended disclosure paths are restricted.
- Active product increment: prepare the immutable v3.109 candidate-image and live-acceptance preflight without changing the accepted Azure state.
- Next authorized product increment: validate an independently restored copy of the accepted v3.36 database, immutable candidate image, live reporting, Azure recovery and rollback, followed by Microsoft Entra and live tenant-isolation acceptance before any v3.109 promotion. The approved bounded scanned-PDF path and later Issue #236 capabilities remain preserved follow-on work.

## Recovery procedure

Before starting an increment:

1. Compare the active development branch with the current frozen commit.
2. Search for an existing candidate branch, pull request, issue update, or release before creating new work.
3. Reconcile this record to the verified GitHub state and update it only when that state changes.
4. Continue from the active roadmap issue and the next authorized increment.
5. For a release candidate, run fresh reconstruction, SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy/infrastructure, CodeQL, and regression gates.
6. Close the controlled validation pull request without merge and freeze only after every required gate is green.

## Standing controls

- Preserve `main`, `development/v1.17`, `release/v1.16`, and every frozen release.
- GitHub controls build state; client-side or conversation state cannot establish release state.
- Human-First Communications and Human Trust & Comprehension doctrine apply throughout the product.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Preserve tenant, sensitivity, disclosure, provenance, human-authority, frozen-history, Azure cost/identity/deployment, visual, reporting, date/time, and release-version controls.
- Never place credentials, confidential Protected Member information, personal information, investigation content, or secrets in this file.
