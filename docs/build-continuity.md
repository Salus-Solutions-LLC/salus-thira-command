---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 17:35 CDT
current_frozen_release: v3.113
current_frozen_commit: 9d9873203fffd8c8ae477123ea94eb35b27c2acd
active_development_branch: development/salcapa-platform
current_development_head: 9d9873203fffd8c8ae477123ea94eb35b27c2acd
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 370
active_increment: issue_337_v3113_immutable_image_publication
last_completed_increment: issue_337_v3113_exact_head_all_20_green_frozen
candidate_release: v3.113
validation_pr: 374
validation_branch: candidate/v3.113-image-activation
validation_base: main
validation_head: pending_exact_final_head_after_continuity_commit
validation_gate_state: controlled_validation_in_progress
failed_workflows: salcapa_build_continuity_stale_candidate_release
first_root_failing_gate: demo_deployment_continuity_candidate_release_alignment
root_cause: frozen_v3113_was_recorded_but_candidate_release_remained_none
repair_head: pending_exact_final_head_after_this_commit
repair_summary: align_candidate_release_with_current_frozen_v3113_for_image_publication_stage
genuine_blockers: none
next_authorized_step: validate_PR_374_close_without_merge_advance_exact_green_activation_head_to_development_trigger_protected_v3113_image_publication_capture_digest_then_prepare_exact_application_promotion
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.113 is frozen** at exact commit `9d9873203fffd8c8ae477123ea94eb35b27c2acd` on `release/v3.113` after all 20 required workflow families passed on controlled validation PR #373.
- PR #373 was closed without merge. The exact validated release head advanced by non-force fast-forward to `development/salcapa-platform` before the immutable release branch was created.
- The accepted Azure development demonstration still runs v3.112. No application deployment, DNS change, credential creation, or public production cutover has occurred for v3.113.
- Controlled validation PR #374 now governs only the v3.113 immutable-image activation record. Its source release is `release/v3.113` and its source commit is the exact frozen v3.113 head.
- The image-publication workflow remains passwordless and scoped to the existing approved Azure development environment. It builds the exact frozen release, checks non-root/runtime identity, and publishes an immutable Azure Container Registry digest before any application promotion may begin.
- Issue #368 archive/current-runtime separation remains preserved in frozen v3.113: immutable v3.43 evidence verification cannot overwrite the current interface.
- No blocker currently requires Marc. If the protected Azure environment pauses for an explicit approval that cannot be performed through available authorized tools, that specific approval will be the only human action requested.

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
4. Distinguish the accepted deployed demonstration from development candidates and frozen releases.
5. Treat newer GitHub work, a failed candidate, a changed active increment, or a newer development head as stale/inconsistent continuity until reconciled.
6. Update this record only from verifiable GitHub state. Do not infer billing or financial readiness from repository or workflow activity.

## Standing controls

- Preserve `main`, `development/v1.17`, `release/v1.16`, and every frozen release.
- After all required gates are green, close the controlled validation pull request without merge, then advance only the exact verified green head by the governed non-force path.
- Preserve security, tenant isolation, sensitivity, disclosure, provenance, human authority, recovery, rollback, frozen-history, Azure identity/deployment boundaries, accessibility, reporting, date/time, and release-version controls.
- Human-First Communications and Human Trust & Comprehension doctrine remain in force.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.
