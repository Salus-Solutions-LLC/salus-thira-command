---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 20:11 CDT
current_frozen_release: v3.110
current_frozen_commit: 935f0b7bea72375adc936f7904f4f74c2eb99643
active_development_branch: development/salcapa-platform
active_roadmap_issue: 124
active_increment: issue_124_v311_report_disclosure_repair
last_completed_release: v3.110
candidate_release: v3.111
validation_pr: 274
validation_gate_state: github_validation_running
genuine_blockers: v310_report_disclosure_gate_failed_v311_validation_entra_recovery_and_rollback_acceptance_missing
next_authorized_increment: issue_124_v311_report_disclosure_repair_validation
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
- Current candidate: **v3.111** at controlled [validation PR #274](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/274) is the bounded successor repair for the report-disclosure defect found by live-reporting acceptance. The pull request must be closed without merge. Frozen v3.110 and every earlier frozen release remain immutable.
- Last completed development increment: [workflow run 34536243545](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34536243545) published exact frozen v3.110 commit [`935f0b7bea72375adc936f7904f4f74c2eb99643`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/935f0b7bea72375adc936f7904f4f74c2eb99643) as immutable image digest `sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44` on 10 September 2026 at 17:14 CDT. The workflow verified the frozen branch and commit, runtime version, non-root execution, workload identity, Azure target, and scoped registry authority. It created no mutable `latest` tag, deployed no application, changed no traffic, and did not modify the accepted v3.36 database.
- Publication validation: [PR #267](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/267) passed all 20 required workflow families on exact activation head [`c5fbcabf0cf655aeb2d18dbe48a87ceb7e21a635`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/c5fbcabf0cf655aeb2d18dbe48a87ceb7e21a635) and was closed without merge before that exact commit advanced to the governed development branch. The [immutable-image publication contract](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-image-publication-contract.md) binds publication to a separately governed activation, matching frozen release branch and exact commit, runtime release identity, immutable image labels, non-root execution, workload identity, scoped registry authority, and SHA-256 digest.
- Live-copy migration acceptance: [workflow run 34545773447](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34545773447) completed successfully on 10 September 2026 at 19:29 CDT. Exact frozen v3.110 and its published immutable image migrated an independently restored 15-minute point-in-time copy of the accepted v3.36 PostgreSQL database. The run verified three fictional Protected Member environments, 24 governed personas, three Draft baseline assessments, and three cross-functional journey records. Source-database and running-application state hashes remained unchanged, and the temporary Container Apps job and restored database were removed. [PR #272](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/272) passed all 20 required workflow families on exact head [`a8d0ff1dec5309026d7c4160596c13cb72ef7fcd`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/a8d0ff1dec5309026d7c4160596c13cb72ef7fcd) and was closed without merge before that commit advanced to development.
- Migration and recovery rehearsal: the accepted-v3.36 rehearsal checks out exact frozen commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b), verifies pinned source identities, migrates its governed demonstration baseline into the current runtime without changing accepted records, verifies immutable report-snapshot integrity, adds the three fictional environments, and exercises tenant-scoped restore and rollback without changing the other tenants. SQLite, PostgreSQL 16, and the production container passed. [Validation PR #260](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/260) passed all 19 workflow families on exact head [`98edaa7b7731d64c67761d02b0de7286fb905cbe`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/98edaa7b7731d64c67761d02b0de7286fb905cbe) and was closed without merge. No Azure resource was contacted or changed by the rehearsal.
- Exact-image boundary: [validation PR #262](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/262) passed all 20 workflow families on exact head [`c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a) and was closed without merge. The new preflight rebuilt exact frozen v3.109, verified its pinned Dockerfile, runtime and dependency identities, checked non-root runtime packaging and source labels, and produced trace evidence without publication, deployment, traffic, cost, or Azure changes. It also verified that v3.109 predates the Issue #124 fixture capability and therefore cannot by itself satisfy the maintained-demonstration requirement.
- Genuine blocker to demonstration promotion: the reporting gate found that Protected Member roles could retrieve Draft report snapshots and mutable internal report previews. Promotion remains closed. The v3.111 successor candidate limits Protected Member report discovery and delivery to hash-verified Released snapshots while preserving internal Salus preview work. Full GitHub validation, Microsoft Entra identity and tenant-isolation acceptance, Azure recovery, and Azure rollback remain required. This does not block safe repository work; the accepted Azure deployment remains unchanged.
- Demonstration checkpoint: the [governed demonstration continuity record](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/demo-deployment-continuity.md) verifies that the most recent successful application-deployment workflow promoted v3.36 at `63d513605f908d3308bb5dd1bbdbf1061878452b` on 06 September 2026 at 13:18 CDT. Its acceptance covered live runtime readiness and identity/dependency configuration, not the full three-member Issue #124 journey.
- Last accepted architecture: the [scanned-PDF page-rendering design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-scanned-pdf-page-rendering-design.md) extends the approved handwriting and expanded-OCR design with embedded-text-first inspection, page-specific authority and purpose, local hash-pinned rendering, exact PDF-point and rendered-pixel transforms, ephemeral page bytes, independent source comparison, and low-cost graceful degradation. Exact page coordinates and authorized geographic coordinates remain preserved and usable; only unintended disclosure paths are restricted.
- Active product increment: validate the v3.111 report-release boundary repair without changing the running application or traffic.
- Next authorized product increment: complete controlled GitHub validation of v3.111, then repeat immutable-image and live reporting acceptance before Azure recovery and rollback, Microsoft Entra and live tenant-isolation acceptance. The approved bounded scanned-PDF path and later Issue #236 capabilities remain preserved follow-on work.

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
