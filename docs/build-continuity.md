---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 17:27 CDT
current_frozen_release: v3.112
current_frozen_commit: 1d1759375d37b7de884331c06833de8c727ac5af
active_development_branch: development/salcapa-platform
current_development_head: ca8e75f6aaba11f175e7030d2d2a71ad51e25692
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 370
active_increment: issue_337_v3113_phase1_release_validation
last_completed_increment: issue_337_issue_360_phase_1_exact_head_all_20_green_promoted_to_development
candidate_release: v3.113
validation_pr: pending
validation_branch: candidate/v3.113-phase1-aesthetic
validation_base: main
validation_head: ca8e75f6aaba11f175e7030d2d2a71ad51e25692
validation_gate_state: local_verified_github_pending
failed_workflows: salcapa_build_continuity
first_root_failing_gate: continuity_candidate_release_identity_mismatch
root_cause: runtime_release_identity_advanced_to_v3.113_before_continuity_metadata_recorded_candidate_release
repair_head: pending_current_development_commit
repair_summary: record_v3.113_candidate_identity_and_governed_full_validation_path_without_changing_frozen_v3.112_or_Azure_demo
genuine_blockers: none
next_authorized_step: create_controlled_v3.113_validation_candidate_run_all_20_gate_families_close_without_merge_freeze_exact_green_head_publish_immutable_image_then_promote_exact_tested_artifact_to_Azure_development
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, pull requests, Actions results, issues, frozen releases, and deployment acceptance evidence control whenever they disagree with this file.

## Current verified checkpoint

- Frozen release remains **v3.112** at `1d1759375d37b7de884331c06833de8c727ac5af`; the accepted Azure development demonstration remains unchanged.
- The exact Issue #337 + Issue #360 Phase 1 visual candidate `93ef7a4d5ab2f0ea0a730469849f4c0ddc3e8a18` passed all **20** required workflow families in PR #372. PR #372 was closed without merge and that exact validated head advanced by non-force fast-forward to `development/salcapa-platform`.
- The release-preparation lineage now identifies the bounded Phase 1 milestone as candidate **v3.113**. Release notes describe the visible light-airy refinement and the Issue #368 archive/runtime isolation control; `salcapa_runtime.py` reports `3.113` for the candidate.
- Issue #368 archive/current-runtime separation is retained: immutable v3.43 evidence is verified outside current runtime/UI source and regression controls fail closed if historical reconstruction mutates current interface files.
- Issue #337 with Issue #360 Phase 1 remains the release scope: light-airy Salus surfaces, restrained navigation/header hierarchy, plain-language page framing, lower cognitive load, and preserved governed access, provenance, evidence, human-authority, recovery, and rollback controls.
- The development continuity failure after release identification was deterministic metadata sequencing only: runtime identity advanced to v3.113 before this continuity record declared the candidate. This record repairs that mismatch without changing the product runtime.
- No blocker requires Marc. The next authorized step is controlled validation of the exact v3.113 candidate, followed only after all-green evidence by immutable freeze, image publication, and promotion of the exact tested artifact to the existing Azure development demonstration.

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
