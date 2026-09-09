---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 13:25 CDT
current_frozen_release: v3.100
current_frozen_commit: b7f54281d254511c5440897d74c427031d24cabe
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: safe_text_processing_candidate_validation
last_completed_release: v3.100
candidate_release: v3.101
validation_pr: 231
validation_gate_state: github_validation_running
genuine_blockers: none
next_authorized_increment: inert_document_extraction_gap_review
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

- Current frozen release: **v3.100** at `b7f54281d254511c5440897d74c427031d24cabe`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The next review must preserve immutable originals, exact source-to-derived lineage, tenant/sensitivity boundaries, explicit processing state and uncertainty, and human qualification before authoritative use. [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: role-aware contextual Add Information actions reuse the existing generic-material store, prepopulate the current authorized assessment or SalINTEL investigation as a server-validated proposal, preserve an append-only audit event, and remain Awaiting Human Review until a qualified person performs governed linking. A context proposal cannot create a finding, decision, authority, disclosure, scope change, charge, or other authoritative state.
- Last controlled validation: [PR #230](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/230), closed without merge after all 16 workflow families passed on the exact frozen commit.
- Current candidate: **v3.101** in controlled [PR #231](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/231); GitHub validation is running and the pull request must be closed without merge.
- Genuine blockers: none.
- Active product increment: validate the first bounded Issue #131 slice: inert-text extraction with exact source hashes, separate derived records, server-selected processor/version, failure-safe source handling, tenant/sensitivity-scoped search, independent human review, and portable backup/recovery inclusion. Derived text remains **Derived — Unverified** and **Awaiting Human Review** until a different authorized person records review; review confirms representation only and cannot establish source truth, evidence, intelligence, findings, decisions, disclosure, cost, or operational authority.
- Next authorized product increment: after v3.101 validation, review safe non-executing document extraction and metadata needs before adding broader document, photo/map, audio, video, entity-suggestion, duplicate-analysis, or transcription workers.

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
