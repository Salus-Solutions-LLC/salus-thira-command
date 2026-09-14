---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 17:11 CDT
current_frozen_release: v3.112
current_frozen_commit: 1d1759375d37b7de884331c06833de8c727ac5af
active_development_branch: development/salcapa-platform
current_development_head: b819b8e0c981f6702f06760c45852371b525e34e
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 368
active_increment: issue_337_issue_360_phase_1_full_milestone_validation
last_completed_increment: issue_368_archive_runtime_isolation_and_visual_candidate_repair
candidate_release: none
validation_pr: 372
validation_branch: validation/issue-337-phase1-current
validation_base: main
validation_head: b819b8e0c981f6702f06760c45852371b525e34e
validation_gate_state: controlled_validation_in_progress
failed_workflows: none_on_exact_candidate_at_validation_start
first_root_failing_gate: none
root_cause: none
repair_head: b819b8e0c981f6702f06760c45852371b525e34e
repair_summary: isolated_archive_verification_non_root_runtime_navigation_composition_light_brand_acceptance_and_operating_model_copy_are_aligned
genuine_blockers: none
next_authorized_step: complete_PR_372_full_gates_close_without_merge_then_freeze_exact_green_candidate_and_promote_exact_tested_artifact_to_Azure_development
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, pull requests, Actions results, issues, frozen releases, and deployment acceptance evidence control whenever they disagree with this file.

## Current verified checkpoint

- Frozen release remains **v3.112** at `1d1759375d37b7de884331c06833de8c727ac5af`; the accepted Azure development demonstration remains unchanged.
- The exact coherent Phase 1 visual candidate is `b819b8e0c981f6702f06760c45852371b525e34e` from `development/salcapa-platform`.
- Issue #368 archive/current-runtime separation now passes SQLite, PostgreSQL 16, production-container, non-root container-runtime, functional validation, dependency/security, and CodeQL checks on the exact candidate.
- Issue #337 with Issue #360 Phase 1 is present on the exact candidate: light-airy Salus surfaces, restrained navigation/header hierarchy, plain-language page framing, and updated deterministic visual acceptance.
- Controlled validation PR #372 is open from `validation/issue-337-phase1-current` at the exact candidate head. It must be closed without merge after the complete milestone gate family finishes.
- No blocker requires Marc. The next authorized step is to complete full validation, then freeze and promote only the exact green artifact.

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
- Controlled validation PRs remain governed and are closed without merge where required; only an exact verified green head may advance by governed non-force fast-forward.
- Preserve security, tenant isolation, sensitivity, disclosure, provenance, human authority, recovery, rollback, frozen-history, Azure identity/deployment boundaries, accessibility, reporting, date/time, and release-version controls.
- Human-First Communications and Human Trust & Comprehension doctrine remain in force.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.
