---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 08 September 2026 23:11 CDT
current_frozen_release: v3.92
current_frozen_commit: 8a98997a5f3d7102d0a6f59bb3fc2a96ca8933d3
active_development_branch: development/salcapa-platform
active_roadmap_issue: 213
active_increment: mission_map_deeper_prove_traceability
last_completed_release: v3.92
candidate_release: v3.93
validation_pr: pending
validation_gate_state: local_verified_github_pending
genuine_blockers: none
next_authorized_increment: mission_map_objective_effectiveness_views
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

- Current frozen release: **v3.92** at `8a98997a5f3d7102d0a6f59bb3fc2a96ca8933d3`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #213](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/213), Mission Map and Mission Structure.
- Last completed increment: Mission Map keyboard, focus, screen-reader, high-contrast, conventional-list, touch-target, and reduced-motion accessibility support.
- Last controlled validation: [PR #220](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/220), closed without merge after all 15 workflow families passed.
- Current candidate: v3.93 deeper Mission Map PROVE traceability; controlled validation pull request pending.
- Genuine blockers: none.
- Active product increment: deeper Mission Map PROVE traceability.
- Next authorized product increment: Mission Map objective-effectiveness views.

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
