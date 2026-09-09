---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 11:57 CDT
current_frozen_release: v3.99
current_frozen_commit: e916a71e57d0ad77d40826cea27bc0916967db26
active_development_branch: development/salcapa-platform
active_roadmap_issue: 133
active_increment: governed_contextual_material_intake_validation
last_completed_release: v3.99
candidate_release: v3.100
validation_pr: 230
validation_gate_state: required_gates_running
genuine_blockers: none
next_authorized_increment: contextual_intake_acceptance_or_repair
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

- Current frozen release: **v3.99** at `e916a71e57d0ad77d40826cea27bc0916967db26`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133), contextual Add Material actions under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The candidate reuses the existing governed material store and records the authorized workspace as a server-validated proposal awaiting human review; it does not create an authoritative link automatically. [Issues #154](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/154) and [#159](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/159) are completed and closed.
- Last completed increment: explicit Protected Membership renewal treatment and decision authority, cancellation-notice period and terms, repricing terms, period-aware service-credit grants and expiration, bounded rollover, versioned conversion tables, server-verified conversions, and independently approved manual consumption corrections. Released member views explain the applicable lifecycle and capacity without exposing Salus-only economics. Nothing renews, reprices, cancels, charges, invoices, changes scope/tier, authorizes partner work, or establishes a customer commitment automatically.
- Last controlled validation: [PR #229](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/229), closed without merge after all 15 workflow families passed on the exact frozen commit.
- Current candidate: **v3.100** on `candidate/v3.100-contextual-intake`; controlled validation [PR #230](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/230) is open in draft and must be closed without merge.
- Genuine blockers: none.
- Active product increment: validate role-aware contextual intake across current assessment and SalINTEL investigation workspaces, direct generic-material preservation, append-only proposed context, tenant and sensitivity boundaries, deterministic reconstruction, and explicit human review before governed linking.
- Next authorized product increment: accept or safely repair v3.100 after every required gate completes; after acceptance, continue to safe extraction, transcription, search, and analyst triage under Issue #131.

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
