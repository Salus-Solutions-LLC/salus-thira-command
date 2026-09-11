---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 11 September 2026 10:01 CDT
current_frozen_release: v3.111
current_frozen_commit: 8bf4614ec79a27641c40dc1a21e1790746a08604
active_development_branch: development/salcapa-platform
active_roadmap_issue: 124
active_increment: issue_124_v311_azure_recovery_acceptance
last_completed_release: v3.111
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: v311_azure_recovery_and_rollback_acceptance_missing
next_authorized_increment: issue_124_v311_azure_recovery_acceptance
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

- Current frozen release: **v3.111** at [`8bf4614`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8bf4614ec79a27641c40dc1a21e1790746a08604) on `release/v3.111`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), governed maintenance and promotion of the Azure development demonstration with three deterministic fictional Protected Member environments. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) remains open and its approved scanned-PDF implementation is preserved as the next product-capability increment after the materially lagging demonstration is made promotion-ready.
- Last completed increment: v3.111 enforces the report release boundary found missing during live-reporting acceptance. Protected Members cannot discover or retrieve Draft, Reviewed, or Approved report work, while released JSON, CSV, and printable HTML are derived from the same immutable, hash-verified Released snapshot. Internal Salus previews and human release authority remain intact.
- Last controlled validation: all 20 required workflow families passed on final checkpoint commit [`8bf4614`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8bf4614ec79a27641c40dc1a21e1790746a08604), including SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy/infrastructure, CodeQL, deterministic reconstruction, and archived capability gates. [Checkpoint PR #275](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/275) was closed without merge. The prior [validation PR #274](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/274) also passed all 20 families and was closed without merge.
- Current candidate: none. [Controlled validation PR #288](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/288) passed all 20 required workflow families on exact head [`22de9cc`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/22de9cc1841a136ce75acdb436fb7fb99b67ca36), was closed without merge, and that exact commit advanced to development. Frozen v3.111 and every earlier frozen release remain immutable.
- Last completed development increment: [workflow run 34553461921](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34553461921) published exact frozen v3.111 commit [`8bf4614ec79a27641c40dc1a21e1790746a08604`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8bf4614ec79a27641c40dc1a21e1790746a08604) as immutable image digest `sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311` on 10 September 2026 at 21:10 CDT. The workflow verified the frozen branch and commit, runtime version, non-root execution, workload identity, Azure target, and scoped registry authority. It created no mutable `latest` tag, deployed no application, changed no traffic, and did not modify the accepted v3.36 database. The prior v3.110 image remains immutable and was not promoted.
- Publication validation: [PR #276](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/276) passed all 20 required workflow families on exact activation head [`88ef924`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/88ef92479777bcd002cc6717e57cc6769a5a7725) and was closed without merge before that exact commit advanced to the governed development branch. The [immutable-image publication contract](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-image-publication-contract.md) binds publication to a separately governed activation, matching frozen release branch and exact commit, runtime release identity, immutable image labels, non-root execution, workload identity, scoped registry authority, and SHA-256 digest.
- Live-copy migration acceptance: [workflow run 34557442913](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34557442913) completed successfully on 10 September 2026 at 22:24 CDT. Exact frozen v3.111 and its published immutable image migrated an independently restored 15-minute point-in-time copy of the accepted v3.36 PostgreSQL database. The run verified three fictional Protected Member environments, 24 governed personas, three Draft baseline assessments, and three cross-functional journey records. Source-database and running-application state hashes remained unchanged, and the temporary Container Apps job and restored database were removed. [PR #277](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/277) passed all 20 required workflow families on exact head [`e94ffd9`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/e94ffd9d55708df9513c4545227ed56dddc5c364) and was closed without merge before that commit advanced to development. This gate establishes live-copy schema and fixture compatibility; it does not establish live report delivery or deployment acceptance.
- Live-reporting acceptance: [workflow run 34605204344](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34605204344) completed successfully on 11 September 2026 at 08:49 CDT. Exact frozen v3.111 and its immutable image verified the report-release boundary against an isolated 15-minute restore of the accepted v3.36 PostgreSQL database. The run passed three-fictional-environment restriction, JSON/CSV/printable-HTML delivery, Draft exclusion, cross-member denial, immutable released snapshots, tamper rejection, refreshed short-lived workload identity, registry digest verification, and source-database and running-application preservation. No scalar governed application value was excluded; Azure-equivalent empty optional collections and unordered response collections were canonicalized before comparison. The accepted application and source database remained unchanged, and the temporary Container Apps job and restored database were removed. Live reporting is accepted; Microsoft Entra identity and tenant-isolation acceptance is now the active gate.
- Microsoft Entra identity and tenant-isolation acceptance: [workflow run 34613330596](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34613330596) completed successfully on 11 September 2026 at 10:01 CDT. The accepted v3.36 demonstration passed tenant-specific Entra discovery, exact redirect, passwordless managed-identity client authentication, no-runtime-secret configuration, and anonymous-session denial. Exact frozen v3.111 and its immutable image then passed an isolated three-fictional-tenant exercise proving server-derived tenant, role, and clearance; cross-tenant audit isolation; and fail-closed handling of unknown, disabled, foreign-tenant, invalid-issuer, invalid-audience, and replay cases. No interactive human login was represented. The accepted application, database, and traffic remained unchanged, and the temporary consumption job was removed.\n- Migration and recovery rehearsal: the accepted-v3.36 rehearsal checks out exact frozen commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b), verifies pinned source identities, migrates its governed demonstration baseline into the current runtime without changing accepted records, verifies immutable report-snapshot integrity, adds the three fictional environments, and exercises tenant-scoped restore and rollback without changing the other tenants. SQLite, PostgreSQL 16, and the production container passed. [Validation PR #260](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/260) passed all 19 workflow families on exact head [`98edaa7b7731d64c67761d02b0de7286fb905cbe`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/98edaa7b7731d64c67761d02b0de7286fb905cbe) and was closed without merge. No Azure resource was contacted or changed by the rehearsal.
- Exact-image boundary: [validation PR #262](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/262) passed all 20 workflow families on exact head [`c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a) and was closed without merge. The new preflight rebuilt exact frozen v3.109, verified its pinned Dockerfile, runtime and dependency identities, checked non-root runtime packaging and source labels, and produced trace evidence without publication, deployment, traffic, cost, or Azure changes. It also verified that v3.109 predates the Issue #124 fixture capability and therefore cannot by itself satisfy the maintained-demonstration requirement.
- Genuine blocker to demonstration promotion: Azure recovery and Azure rollback remain required. Live reporting and Microsoft Entra identity/tenant isolation are accepted. The accepted Azure deployment remains unchanged on v3.36.
- Demonstration checkpoint: the [governed demonstration continuity record](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/demo-deployment-continuity.md) verifies that the most recent successful application-deployment workflow promoted v3.36 at `63d513605f908d3308bb5dd1bbdbf1061878452b` on 06 September 2026 at 13:18 CDT. Its acceptance covered live runtime readiness and identity/dependency configuration, not the full three-member Issue #124 journey.
- Last accepted architecture: the [scanned-PDF page-rendering design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-scanned-pdf-page-rendering-design.md) extends the approved handwriting and expanded-OCR design with embedded-text-first inspection, page-specific authority and purpose, local hash-pinned rendering, exact PDF-point and rendered-pixel transforms, ephemeral page bytes, independent source comparison, and low-cost graceful degradation. Exact page coordinates and authorized geographic coordinates remain preserved and usable; only unintended disclosure paths are restricted.
- Active product increment: verify Azure recovery for exact frozen v3.111 without changing the accepted application, database, traffic, or human authority.
- Next authorized product increment: Azure recovery acceptance before Azure rollback. The approved bounded scanned-PDF path and later Issue #236 capabilities remain preserved follow-on work.

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
