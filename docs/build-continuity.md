---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 16:19 CDT
current_frozen_release: v3.110
current_frozen_commit: 935f0b7bea72375adc936f7904f4f74c2eb99643
active_development_branch: development/salcapa-platform
active_roadmap_issue: 124
active_increment: issue_124_v310_image_publication_activation
last_completed_release: v3.110
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: v310_image_publication_live_v336_database_entra_reporting_recovery_and_rollback_acceptance_missing
next_authorized_increment: issue_124_v310_image_publication_activation
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

- Current frozen release: **v3.110** at [`935f0b7bea72375adc936f7904f4f74c2eb99643`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/935f0b7bea72375adc936f7904f4f74c2eb99643) on `release/v3.110`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), governed maintenance and promotion of the Azure development demonstration with three deterministic fictional Protected Member environments. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) remains open and its approved scanned-PDF implementation is preserved as the next product-capability increment after the materially lagging demonstration is made promotion-ready.
- Last completed increment: v3.110 adds the deterministic three-member fictional demonstration foundation, governed cross-functional SalINTEL/SalTHIRA/SalCAPA/SalOPS/PROVE records, role and tenant preflight, accepted-v3.36 forward-migration and recovery rehearsal, and exact candidate-image boundary. It does not represent human approval, publish an image, deploy an application, change Azure traffic, or authorize production use.
- Last controlled validation: [PR #263](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/263), on which all 20 required workflow families passed on exact frozen v3.110 commit [`935f0b7bea72375adc936f7904f4f74c2eb99643`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/935f0b7bea72375adc936f7904f4f74c2eb99643). The pull request was closed without merge. All 20 development-branch workflow families also passed on the same exact commit before freeze.
- Current candidate: none. Frozen v3.110 and every earlier frozen release remain immutable.
- Last completed development increment: the [immutable-image publication contract](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-image-publication-contract.md) now binds publication to a separately governed activation, a matching frozen release branch and exact commit, runtime release identity, immutable image labels, non-root execution, workload identity, scoped registry authority, and SHA-256 digest. It removes the legacy hard-coded v3.36 source assumption without changing the accepted v3.36 activation. [Validation PR #265](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/265) passed all 20 required workflow families on exact head [`8b033a3200a54350f6fa8344ffacfe1d43642b31`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8b033a3200a54350f6fa8344ffacfe1d43642b31) and was closed without merge. No image was published, no application was deployed, and no Azure traffic or accepted data changed.
- Migration and recovery rehearsal: the accepted-v3.36 rehearsal checks out exact frozen commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b), verifies pinned source identities, migrates its governed demonstration baseline into the current runtime without changing accepted records, verifies immutable report-snapshot integrity, adds the three fictional environments, and exercises tenant-scoped restore and rollback without changing the other tenants. SQLite, PostgreSQL 16, and the production container passed. [Validation PR #260](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/260) passed all 19 workflow families on exact head [`98edaa7b7731d64c67761d02b0de7286fb905cbe`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/98edaa7b7731d64c67761d02b0de7286fb905cbe) and was closed without merge. No Azure resource was contacted or changed by the rehearsal.
- Exact-image boundary: [validation PR #262](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/262) passed all 20 workflow families on exact head [`c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a) and was closed without merge. The new preflight rebuilt exact frozen v3.109, verified its pinned Dockerfile, runtime and dependency identities, checked non-root runtime packaging and source labels, and produced trace evidence without publication, deployment, traffic, cost, or Azure changes. It also verified that v3.109 predates the Issue #124 fixture capability and therefore cannot by itself satisfy the maintained-demonstration requirement.
- Genuine blocker to demonstration promotion: v3.110 is frozen with deterministic fixtures, bounded cross-functional records, repository role/tenant preflight, accepted-v3.36 migration/recovery rehearsal, and candidate-image boundary verified. Publication and acceptance of an immutable v3.110 image, migration of an independently restored copy of the live accepted v3.36 database, Microsoft Entra identity and tenant-isolation acceptance, live reporting, Azure recovery, and Azure rollback remain required. This does not block safe repository work; the accepted Azure deployment remains unchanged.
- Demonstration checkpoint: the [governed demonstration continuity record](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/demo-deployment-continuity.md) verifies that the most recent successful application-deployment workflow promoted v3.36 at `63d513605f908d3308bb5dd1bbdbf1061878452b` on 06 September 2026 at 13:18 CDT. Its acceptance covered live runtime readiness and identity/dependency configuration, not the full three-member Issue #124 journey.
- Last accepted architecture: the [scanned-PDF page-rendering design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-scanned-pdf-page-rendering-design.md) extends the approved handwriting and expanded-OCR design with embedded-text-first inspection, page-specific authority and purpose, local hash-pinned rendering, exact PDF-point and rendered-pixel transforms, ephemeral page bytes, independent source comparison, and low-cost graceful degradation. Exact page coordinates and authorized geographic coordinates remain preserved and usable; only unintended disclosure paths are restricted.
- Active product increment: prepare the separately governed activation for exact frozen v3.110 image publication without changing the running Azure application or traffic.
- Next authorized product increment: validate and apply the v3.110 image activation under the existing protected-environment, cost, workload-identity and registry-authority controls; record the immutable digest; then validate live-data-copy migration, reporting, Azure recovery and rollback, followed by Microsoft Entra and live tenant-isolation acceptance before promotion. The approved bounded scanned-PDF path and later Issue #236 capabilities remain preserved follow-on work.

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
