---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 01:48 CDT
current_frozen_release: v3.95
current_frozen_commit: d315ee95057b337a5bffcf7547d9c0e15042e14d
active_development_branch: development/salcapa-platform
active_roadmap_issue: 154
active_increment: commercial_unbilled_wip_treatment
last_completed_release: v3.95
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: commercial_governed_integration_pathways
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

- Current frozen release: **v3.95** at `d315ee95057b337a5bffcf7547d9c0e15042e14d`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #154](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/154), governed estimating, cost, pricing, and margin management. Its next incomplete authorized increment is unbilled/work-in-progress treatment, with governed integration pathways to follow. [Issue #159](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/159) remains linked for Protected Membership economics.
- Last completed increment: governed, versioned Protected Membership plans and exact portfolio terms; independently reviewed consumption; member-safe released capacity views; and Salus-only recurring-value, cost-to-serve, forecast, and planning-contribution views. Membership remains distinct from investigation Tier 1/2/3, and no automatic charge, invoice, renewal, scope, tier, entitlement-overage, partner, or customer-commitment effect is permitted.
- Last controlled validation: [PR #224](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/224), closed without merge after all 15 workflow families passed on the exact frozen commit. Closed PR #223 was superseded after a narrow Mission Map release-expectation correction and was also not merged.
- Current candidate: none.
- Genuine blockers: none.
- Active product increment: governed unbilled/work-in-progress treatment.
- Next authorized product increment: governed commercial integration pathways after the unbilled/work-in-progress increment passes every required release gate.

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
