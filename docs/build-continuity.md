---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 15:28 CDT
current_frozen_release: v3.102
current_frozen_commit: ab74673425de0b2c6a412382ad708220863879bb
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: pdf_extraction_design_review
last_completed_release: v3.102
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: bounded_pdf_extraction_design_review
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

- Current frozen release: **v3.102** at `ab74673425de0b2c6a412382ad708220863879bb`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The next review must preserve immutable originals, exact source-to-derived lineage, tenant/sensitivity boundaries, explicit processing state and uncertainty, and human qualification before authoritative use. [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: the second bounded Issue #131 slice adds local, non-executing text and limited-metadata extraction for `.docx`, `.xlsx`, and `.pptx` materials. It preserves immutable source hashes and exact processor lineage; enforces package-entry, path, encryption, active-content, expanded-size, part-size, and compression-ratio controls; and rejects macros, embedded objects, legacy binaries, malformed packages, and type mismatches. Formulas are never calculated, cached values and source-stored metadata are explicitly qualified, revision markup remains unresolved, and presentation reading order is identified as approximate. Derived records remain **Derived — Unverified** and **Awaiting Human Review**; review confirms representation only and cannot establish source truth, evidence, intelligence, findings, decisions, disclosure, cost, or operational authority.
- Last controlled validation: [PR #232](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/232), closed without merge after all 17 controlled-pull-request workflow families and the separate candidate-push validation passed on the exact frozen commit.
- Last completed design review: [Safe document extraction design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-safe-document-extraction.md), validated by CI, CodeQL, and contextual-intake checks at `244515af7a808d6ae43cf8a4f6fc9a755327f35e`. The approved first document slice is local, non-executing Office Open XML extraction for `.docx`, `.xlsx`, and `.pptx`; macro-enabled, encrypted, legacy binary, PDF, OCR, image, map, audio, video, embedded-object, external-link, and formula-execution paths remain deferred or rejected.
- Current candidate: none. Controlled [PR #232](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/232) is closed without merge.
- Genuine blockers: none.
- Active product increment: review a separately bounded PDF text and structure worker while preserving the v3.102 immutable-source, derived-record, uncertainty, tenant, sensitivity, review, search, and recovery controls.
- Next authorized product increment: establish and validate the bounded PDF extraction design before implementation. OCR, photo/map, audio, video, entity-suggestion, duplicate-analysis, and transcription workers remain separately gated.

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
