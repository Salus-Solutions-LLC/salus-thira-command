---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 06:22 CDT
current_frozen_release: v3.108
current_frozen_commit: ac50c7b26bc322eb784894de9e8533c1da74649a
active_development_branch: development/salcapa-platform
active_roadmap_issue: 236
active_increment: issue_236_handwriting_and_expanded_ocr_design_approved
last_completed_release: v3.108
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: issue_236_handwriting_and_expanded_ocr_implementation
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

- Current frozen release: **v3.108** at [`ac50c7b26bc322eb784894de9e8533c1da74649a`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/ac50c7b26bc322eb784894de9e8533c1da74649a) on `release/v3.108`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236), native advanced governed visual intelligence, geospatial metadata, handwriting, expanded OCR, mapping, and separately governed facial/biometric capability. [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) are completed and closed under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128).
- Last completed increment: v3.108 adds the native object and visible-condition processing contract: a hash-pinned deployment-supplied local processor boundary, immutable source/job/model/profile/vocabulary/transform lineage, derived-unverified source-region suggestions, limitations and alternatives, independent human comparison and correction, tenant and sensitivity controls, fail-closed artifact validation, manual fallback, native Information Review guidance, and portable backup/recovery. It adds no standing GPU, paid external service, runtime model download, or automatic authority.
- Last controlled validation: [PR #246](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/246), on which all 17 controlled-pull-request workflow families passed on exact v3.108 commit [`ac50c7b26bc322eb784894de9e8533c1da74649a`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/ac50c7b26bc322eb784894de9e8533c1da74649a). The pull request was closed without merge.
- Current candidate: none.
- Genuine blockers: none.
- Last accepted architecture: the [object and visible-condition analysis design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-object-condition-analysis-design.md) defines local request-driven processing, exact source-region and transform lineage, server-controlled model and vocabulary profiles, neutral operational categories, strict person-related boundaries, independent review, proposal-only downstream references, manual operating capability, and low-cost CPU-first deployment.
- Active product increment: the [handwriting recognition and expanded OCR design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/candidate/issue-236-handwriting-ocr-design/docs/salcapa-handwriting-expanded-ocr-design.md) is approved for controlled validation. It defines native local printed, handwritten, mixed, targeted-region, and scanned-PDF recognition; explicit uncertainty and append-only correction; server-controlled language and processor profiles; and a separately enabled external-provider route with data-region, retention, identity, transmission, and spend controls.
- Next authorized product increment: after this design checkpoint passes, implement the bounded handwriting and expanded-OCR record, worker, review, correction, recovery, and interface contracts. Maps/plans and separately governed facial/biometric functions remain authorized native follow-on increments under Issue #236.

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
