---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 19:20 CDT
current_frozen_release: v3.103
current_frozen_commit: 459d7532d5eaa6e27c6facd6d39de55a7171837a
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: image_metadata_ocr_candidate_validation
last_completed_release: v3.103
candidate_release: v3.104
validation_pr: 234
validation_gate_state: github_validation_running
genuine_blockers: none
next_authorized_increment: complete_v3_104_validation
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

- Current frozen release: **v3.103** at `459d7532d5eaa6e27c6facd6d39de55a7171837a`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The next review must preserve immutable originals, exact source-to-derived lineage, tenant/sensitivity boundaries, explicit processing state and uncertainty, and human qualification before authoritative use. [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: the third bounded Issue #131 slice adds local, request-driven embedded-text and page-structure extraction for PDF materials in an isolated, resource-limited child process. It preserves immutable originals, exact source hashes, processor lineage, page boundaries, limited source-stored metadata, tenant and sensitivity boundaries, search, recovery, and independent representation review. Encrypted, malformed, repair-dependent, oversized, active-content, embedded-file, and type-mismatched PDFs fail closed. The worker does not perform OCR, rendering, forms, signatures, attachments, remote access, script execution, external actions, or semantic layout reconstruction. Derived records remain **Derived — Unverified** and **Awaiting Human Review**; review confirms representation only and cannot establish source truth, evidence, intelligence, findings, decisions, disclosure, cost, or operational authority.
- Last controlled validation: [PR #233](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/233), closed without merge after all 17 controlled-pull-request workflow families and the separate candidate-push validation passed on the exact frozen commit.
- Last completed design review: [Safe image metadata and OCR design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-safe-image-ocr-extraction.md), validated by CI, CodeQL, and contextual-intake checks at `23243af9b1be71f060a44fdd1c05d72fbd3e42e5`. The approved first slice is local, request-driven metadata review and English printed-text OCR for single-frame JPEG and PNG sources. Exact GPS coordinates, broader formats and languages, image interpretation, facial or biometric work, object classification, map analysis, image enhancement, scanned-PDF rendering, and external services remain deferred.
- Current candidate: **v3.104** at `1bb2faf0f0e05e49d350a6d0543386dbf26b5358`. Controlled [PR #234](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/234) is open for validation only and must be closed without merge.
- Genuine blockers: none.
- Active product increment: validate the v3.104 bounded JPEG/PNG metadata and English printed-text OCR candidate while preserving immutable originals, exact source-to-derived lineage, restricted hidden metadata, explicit recognition uncertainty, tenant and sensitivity boundaries, independent human review, process isolation, and low-cost Azure controls.
- Next authorized product increment: complete the full v3.104 validation matrix, close PR #234 without merge, and freeze only if every required gate is green. Scanned-PDF rendering, broader image formats and languages, photo/map interpretation, audio, video, entity-suggestion, duplicate-analysis, and transcription workers remain separately gated.

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
