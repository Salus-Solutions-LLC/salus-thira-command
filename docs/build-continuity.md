---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 22:42 CDT
current_frozen_release: v3.105
current_frozen_commit: 9b2e03144b1a68b64c4ce64b70536f63b47949ef
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: governed_suggestions_duplicate_candidate
last_completed_release: v3.105
candidate_release: none
validation_pr: none
validation_gate_state: all_required_gates_green
genuine_blockers: none
next_authorized_increment: v3.106_implementation_candidate
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

- Current frozen release: **v3.105** at [`9b2e03144b1a68b64c4ce64b70536f63b47949ef`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/9b2e03144b1a68b64c4ce64b70536f63b47949ef) on `release/v3.105`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: the fifth bounded Issue #131 slice adds local, request-driven transcription for PCM WAV, single-stream MP3, and MP4 materials with one AAC audio stream. Fixed server-controlled FFprobe/FFmpeg processing extracts and normalizes audio without analyzing video frames. Pinned, hash-verified local whisper.cpp components prepare English spoken-word review aids inside an isolated, resource-limited process. Original materials remain immutable, source-to-normalized-audio-to-transcript lineage is explicit, and tenant and sensitivity controls are preserved. Results remain **Derived — Unverified** and **Awaiting Human Review**; they cannot establish source truth, speaker identity, biometric identity, emotion, credibility, evidence, intelligence, findings, decisions, disclosure, cost, or authority. Manual source review remains available when processing is unavailable. The increment adds no paid Azure speech service, standing worker, queue, GPU, or automatic scale-out.
- Last controlled validation: [PR #237](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/237), closed without merge on 09 September 2026 after all 17 controlled-pull-request workflow families passed on the exact frozen commit. The candidate also passed fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure infrastructure, CodeQL, deterministic reconstruction, recovery, contextual-intake, and existing capability regression checks.
- Current candidate: none.
- Genuine blockers: none.
- Issue #131 acceptance status: the material-processing foundation is accepted, but Issue #131 remains open. The governed [acceptance and gap review](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-material-processing-acceptance-review.md) identifies entity/date/location suggestions, duplicate/relationship review, and the integrated fictional analyst journey as the remaining work.
- Last completed design review: the [governed suggestions and duplicate-review design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-governed-suggestions-and-duplicate-review.md) defines local tenant-reference matching, ambiguity-preserving date/time suggestions, exact-hash duplicate review, bounded text near-duplicate comparison, immutable initial proposals, append-only correction history, and destination-specific governed-link review.\n- Active product increment: implement and validate the bounded v3.106 governed suggestions and duplicate-review candidate under Issue #131.\n- Next authorized product increment: the bounded v3.106 implementation candidate. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) preserves the approved advanced visual-intelligence requirements—including authorized exact GPS/geospatial handling, image interpretation, object and condition classification, handwriting recognition, broader or approved external OCR, maps and floor plans, and separately governed facial/biometric capability. The bounded v3.104-v3.105 exclusions are first-slice controls, not permanent product exclusions.

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
