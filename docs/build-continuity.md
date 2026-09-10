---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 09 September 2026 21:25 CDT
current_frozen_release: v3.104
current_frozen_commit: a2e47f735a0267429f471455690cb22375f19ee9
active_development_branch: development/salcapa-platform
active_roadmap_issue: 131
active_increment: audio_video_transcription_candidate_validation
last_completed_release: v3.104
candidate_release: v3.105
validation_pr: pending
validation_gate_state: github_validation_running
genuine_blockers: none
next_authorized_increment: controlled_validation_pr
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

- Current frozen release: **v3.104** at `a2e47f735a0267429f471455690cb22375f19ee9`.
- Active development line: `development/salcapa-platform`.
- Active roadmap: [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131), safe derived extraction, transcription, search, and analyst triage under parent [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128). The next review must preserve immutable originals, exact source-to-derived lineage, tenant/sensitivity boundaries, explicit processing state and uncertainty, and human qualification before authoritative use. [Issue #133](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/133) is completed and closed.
- Last completed increment: the fourth bounded Issue #131 slice adds local, request-driven selected metadata review and English printed-text OCR for single-frame JPEG and PNG materials in an isolated, resource-limited process. It preserves immutable originals, exact source hashes, processor and English-language-data identity, tenant and sensitivity boundaries, search, recovery, and independent representation review. Type-mismatched, malformed, oversized, decompression-risk, and multi-frame images fail closed. Exact GPS coordinates, image interpretation, facial or biometric work, object classification, handwriting recognition, scanned-PDF rendering, external services, and network access remain excluded. Derived records remain **Derived — Unverified** and **Awaiting Human Review**; review confirms representation only and cannot establish source truth, evidence, intelligence, findings, decisions, disclosure, cost, or operational authority.
- Last controlled validation: [PR #234](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/234), closed without merge after all 17 controlled-pull-request workflow families and the separate candidate-push validation passed on the exact frozen commit.
- Last completed design review: [Safe audio and video transcription design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-safe-audio-video-transcription.md), validated by CI, CodeQL, and contextual-intake checks at `62388d7a4a42009b56beeb82af0aa9b5b3000243`. The approved first slice accepts bounded PCM WAV, MP3, and MP4-with-one-AAC-stream sources; extracts only audio; normalizes it locally; and prepares English spoken-word review aids with a pinned, hash-verified offline model. Video analysis, speaker identity or diarization, biometrics, emotion or credibility inference, sound-event classification, language detection, translation, live monitoring, request-time downloads, external services, and cross-tenant learning remain excluded.\n- Current candidate: **v3.105** at [`77499fee637164300a4e87cbdd70f6bb5d64696d`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/77499fee637164300a4e87cbdd70f6bb5d64696d); controlled validation is in progress.
- Genuine blockers: none.
- Active product increment: validate the exact v3.105 audio/video transcription candidate under Issue #131, preserving immutable originals, source-to-normalized-audio-to-transcript lineage, explicit recognition uncertainty, tenant and sensitivity boundaries, independent human review, resource isolation, graceful manual fallback, and low-cost Azure controls.\n- Next authorized product increment: open and close a controlled v3.105 validation pull request without merge after the candidate-push gates are green. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) preserves the approved advanced visual-intelligence requirements for separately governed increments after the current media-processing foundation.\n
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
