---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 10 September 2026 07:25 CDT
current_frozen_release: v3.108
current_frozen_commit: ac50c7b26bc322eb784894de9e8533c1da74649a
active_development_branch: development/salcapa-platform
active_roadmap_issue: 236
active_increment: issue_236_local_handwriting_and_expanded_ocr_candidate
last_completed_release: v3.108
candidate_release: v3.109
validation_pr: 249
validation_gate_state: github_validation_running
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
- Last controlled validation: [PR #248](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/248), on which all 17 required workflow families passed on exact handwriting and expanded-OCR design commit [`d5a12b3fabb5c8e95bf29c2c86cc06329994c79b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/d5a12b3fabb5c8e95bf29c2c86cc06329994c79b). The pull request was closed without merge. Candidate-branch validation now runs directly without creating a merge path to frozen `main`.
- Current candidate: **v3.109** at [`78262d41cdc5beb767e7110bf74cee816011ef50`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/78262d41cdc5beb767e7110bf74cee816011ef50), under controlled validation in [PR #249](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/249). It adds the native local JPEG/PNG printed, handwritten, mixed, and targeted-region recognition foundation, immutable job/profile/artifact/transform/source-region lineage, explicit alternate and uncertain readings, independent review and append-only correction, manual transcription, interface guidance, and portable backup/recovery hooks. It adds no scanned-PDF rendering or external provider transmission.
- Genuine blockers: none.
- Last accepted architecture: the [handwriting recognition and expanded OCR design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-handwriting-expanded-ocr-design.md) defines source-grounded printed, handwritten, mixed, targeted-region, and scanned-PDF recognition; explicit uncertainty and illegible passages; append-only correction; server-controlled language and local processor profiles; manual transcription; and a separately enabled external-provider route with data-region, retention, identity, transmission, validation, and spend controls.
- Active product increment: validate the bounded v3.109 local recognition candidate under Issue #236 without changing frozen branches or enabling unapproved processor artifacts.
- Next authorized product increment: after v3.109 is frozen, add bounded scanned-PDF page rendering only after embedded-text inspection. The separately enabled external-provider route, maps/plans, and separately governed facial/biometric functions remain authorized follow-on increments under Issue #236.

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
