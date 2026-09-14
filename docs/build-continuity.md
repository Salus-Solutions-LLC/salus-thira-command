---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 17:28 CDT
current_frozen_release: v3.112
current_frozen_commit: 1d1759375d37b7de884331c06833de8c727ac5af
active_development_branch: development/salcapa-platform
current_development_head: b59a0980148beaa0d2806b7e11cd3a40e147b87b
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 370
active_increment: issue_337_v3113_phase1_release_validation
last_completed_increment: issue_337_issue_360_phase_1_exact_head_all_20_green_promoted_to_development
candidate_release: v3.113
validation_pr: 373
validation_branch: candidate/v3.113-phase1-aesthetic
validation_base: main
validation_head: pending_exact_final_head_after_continuity_commit
validation_gate_state: controlled_validation_in_progress
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: release_identity_and_continuity_aligned_for_full_v3.113_validation
genuine_blockers: none
next_authorized_step: run_all_20_gate_families_on_exact_PR_373_head_close_without_merge_freeze_exact_green_head_publish_immutable_image_then_promote_exact_tested_artifact_to_Azure_development
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, pull requests, workflow results, issues, frozen releases, and deployment acceptance evidence control whenever they disagree with this file.

## Current verified checkpoint

- Frozen release remains **v3.112** at `1d1759375d37b7de884331c06833de8c727ac5af`; the accepted Azure development demonstration remains unchanged.
- The exact Issue #337 + Issue #360 Phase 1 visual candidate `93ef7a4d5ab2f0ea0a730469849f4c0ddc3e8a18` passed all **20** required workflow families in PR #372. PR #372 was closed without merge and that exact validated head advanced by non-force fast-forward to `development/salcapa-platform`.
- The release-preparation lineage now identifies the bounded Phase 1 milestone as candidate **v3.113**. Release notes describe the visible light-airy refinement and the Issue #368 archive/runtime isolation control; `salcapa_runtime.py` reports `3.113` for the candidate.
- Controlled validation PR #373 is open from `candidate/v3.113-phase1-aesthetic` to `main`. It is validation-only and must close without merge. Every required workflow family must pass on one exact final head before freeze or deployment.
- Issue #368 archive/current-runtime separation is retained: immutable v3.43 evidence is verified outside current runtime/UI source and regression controls fail closed if historical reconstruction mutates current interface files.
- Issue #337 with Issue #360 Phase 1 remains the release scope: light-airy Salus surfaces, restrained navigation/header hierarchy, plain-language page framing, lower cognitive load, and preserved governed access, provenance, evidence, human-authority, recovery, and rollback controls.
- No blocker requires Marc. After all required PR #373 gates are green, close the controlled validation pull request without merge, freeze the exact green head, publish its immutable image, and promote only that tested artifact to the existing Azure development demonstration.

## Source precedence

1. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.
2. This continuity record after comparison with those GitHub records.
3. Approved architecture and doctrine records referenced by the active milestone.
4. Conversation history only as supporting design context.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

At each build or continuity check:

1. Read this file from `development/salcapa-platform`.
2. Compare it with the exact current development branch head, all open SalCAPA validation PRs, and the latest relevant Actions results.
3. If a candidate exists, record its exact PR/head, base, gate state, and first/root failing gate.
4. Distinguish the accepted deployed demonstration from development candidates.
5. Treat newer GitHub work, a failed candidate, a changed active increment, or a newer development head as stale/inconsistent continuity until reconciled.
6. Update this record only from verifiable GitHub state. Do not infer billing or financial readiness from repository or workflow activity.

## Standing controls

- Preserve `main`, `development/v1.17`, `release/v1.16`, and every frozen release.
- After all required gates are green, close the controlled validation pull request without merge, then advance only the exact verified green head by the governed non-force path.
- Preserve security, tenant isolation, sensitivity, disclosure, provenance, human authority, recovery, rollback, frozen-history, Azure identity/deployment boundaries, accessibility, reporting, date/time, and release-version controls.
- Human-First Communications and Human Trust & Comprehension doctrine remain in force.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.
