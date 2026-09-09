---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 13:41 CDT
current_frozen_release: v3.101
current_frozen_commit: 8d8c4e029a6612050fa697a6e1ee251761b8f61b
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: inert_document_extraction_gap_review
last_completed_release: v3.101
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: bounded_document_extraction_design_review
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

- Current frozen release: **v3.101** at `8d8c4e029a6612050fa697a6e1ee251761b8f61b`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The next review must preserve immutable originals, exact source-to-derived lineage, tenant/sensitivity boundaries, explicit processing state and uncertainty, and human qualification before authoritative use. [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: the first bounded Issue #131 slice provides non-executing text extraction for inert text, CSV, TSV, JSON, XML, log, and EML materials; exact source and derivative hashes; separate derived records; server-selected processor/version; failure-safe handling; tenant- and sensitivity-scoped search; independent human review; and portable backup/recovery coverage. Derived text remains **Derived — Unverified** and **Awaiting Human Review** until a different authorized person records review. Review confirms representation only and cannot establish source truth, evidence, intelligence, findings, decisions, disclosure, cost, or operational authority.
- Last controlled validation: [PR #231](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/231), closed without merge after all 17 controlled-pull-request workflow families and the separate candidate-push validation passed on the exact frozen commit.
- Current candidate: none.
- Genuine blockers: none.
- Active product increment: review safe non-executing document extraction and metadata needs while preserving the v3.101 source/derivative, uncertainty, access, review, and recovery controls.
- Next authorized product increment: define the next bounded document-extraction slice before adding broader document, photo/map, audio, video, entity-suggestion, duplicate-analysis, or transcription workers.

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
