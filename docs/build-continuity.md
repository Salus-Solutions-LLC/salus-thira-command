---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 01:16 CDT
current_frozen_release: v3.106
current_frozen_commit: 0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01
active_development_branch: development/salcapa-platform
active_roadmap_issue: 236
active_increment: issue_236_bounded_design
last_completed_release: v3.106
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: issue_236_geospatial_and_visual_analysis_design
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

- Current frozen release: **v3.106** at [`0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01) on `release/v3.106`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236), native advanced governed visual intelligence, geospatial metadata, handwriting, expanded OCR, mapping, and separately governed facial/biometric capability. [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) are completed and closed under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128).
- Last completed increment: v3.106 adds tenant-scoped references and ambiguity-preserving date, 24-hour time, and location review aids; exact source and derived-content comparison; bounded near-duplicate text review; immutable initial proposals; append-only human correction history; and proposal-only governed links. The integrated Salus-only Information Review interface shows source context, limits, uncertainty, review state, human authority, and what happens next. Suggestions remain **Derived — Unverified** and **Awaiting Human Review** until independently reviewed and cannot establish identity, intelligence, findings, relationships, monitoring, disclosure, scope, cost, or authority.
- Last controlled validation: [PR #238](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/238), closed without merge on 09 September 2026 after all 17 controlled-pull-request workflow families passed on the exact frozen commit. The candidate passed fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure infrastructure, CodeQL, deterministic reconstruction, recovery, contextual-intake, and existing capability regression checks.
- Current candidate: none.
- Genuine blockers: none.
- Issue #131 acceptance status: completed and closed on 10 September 2026. The [final acceptance record](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-material-processing-final-acceptance.md) reconciles v3.101–v3.106 and the integrated fictional analyst journey. [Validation PR #239](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/239) passed all 17 required workflow families and closed without merge.
- Last accepted implementation: the governed [suggestions and duplicate-review design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-governed-suggestions-and-duplicate-review.md) is implemented in v3.106 with local tenant-reference matching, ambiguity-preserving date/time suggestions, exact-hash and bounded near-duplicate review, immutable proposals, append-only correction history, and destination-specific governed-link proposals.
- Active product increment: prepare the first bounded Issue #236 design as a native extension of the established SalCAPA source, provenance, review, tenant, sensitivity, disclosure, audit, backup, and recovery contracts.
- Next authorized product increment: Issue #236 geospatial and visual-analysis design. Begin with authorized exact GPS retention/use and source-region-grounded image interpretation, then sequence object/condition classification, handwriting, expanded OCR, maps/plans, and facial/biometric functions through separate bounded gates.

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
