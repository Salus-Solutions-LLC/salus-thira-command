---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 09:59 CDT
current_frozen_release: v3.97
current_frozen_commit: 93a59ddb3e850a93c22ee3faf78d16cc5a01f57d
active_development_branch: development/salcapa-platform
active_roadmap_issue: 154
active_increment: commercial_management_reporting_completion
last_completed_release: v3.97
candidate_release: v3.98
validation_pr: pending
validation_gate_state: local_verified_github_pending
genuine_blockers: none
next_authorized_increment: commercial_issue_154_acceptance_review
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

- Current frozen release: **v3.97** at `93a59ddb3e850a93c22ee3faf78d16cc5a01f57d`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #154](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/154), governed estimating, cost, pricing, and margin management. Its next incomplete authorized increment is completion of the remaining Salus-only commercial management-reporting requirements. [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128) controls the reusable information-intake architecture; [Issue #159](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/159) remains linked for Protected Membership economics.
- Last completed increment: reusable, tenant-scoped SharePoint/OneDrive and other authorized-repository source identities; immutable exact-version and access-state provenance; byte/hash/access-time evidence only when bytes were accessed; independently approved commercial source links; retained historical basis; explicit newer-version and material-change review cues; tenant isolation; and backup/restore integrity. Registration or access never implies human review or approval, and no source event creates a charge, invoice, recognized revenue, scope/price or membership change, or external transmission.
- Last controlled validation: [PR #227](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/227), closed without merge after all 15 workflow families passed on the exact frozen commit.
- Current candidate: **v3.98**, with its controlled validation pull request pending creation. The candidate adds Salus-only recurring commercial position reporting, evidence-qualified comparative contribution views, current-source checks for approved forecasts, period controls, and export-compatible management output. It does not recognize revenue, margin, or profit or create a charge, invoice, scope authorization, or external transmission.
- Genuine blockers: none.
- Active product increment: validate the remaining Salus-only management-reporting views for recurring value/cost and evidence-qualified highest/lowest planning contribution by domain, tier, and product line without presenting planning contribution as recognized revenue, margin, or profit.
- Next authorized product increment: conduct the governed Issue #154 acceptance review after the management-reporting increment passes every required release gate.

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
