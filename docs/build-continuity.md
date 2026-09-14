---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 12:59 CDT
current_frozen_release: v3.112
current_frozen_commit: 1d1759375d37b7de884331c06833de8c727ac5af
active_development_branch: development/salcapa-platform
current_development_head: d3e3c5626049061171c2db7ff5468a3cfef42178
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 368
active_increment: issue_368_archive_runtime_isolation_repair_validation
last_completed_increment: issue_290_authenticated_advisor_decision_checkpoint
candidate_release: none
validation_pr: 365
validation_branch: validation/issue-337-light-airy-shell
validation_base: main
validation_head: 2b831b6c0a0df9238d01caeb08c419d257d1710c
validation_gate_state: repair_validation_pending
failed_workflows: prior_PR_365_CI; prior_PR_365_CodeQL_Local_Analysis
first_root_failing_gate: prior_PR_365_Reconstruct_and_verify_archived_source
root_cause: archived_v3_43_verification_and_reconstruction_were_coupled_to_current_runtime_source
repair_head: d3e3c5626049061171c2db7ff5468a3cfef42178
repair_summary: v3_43_reconstruction_and_verification_now_default_to_isolated_reference_storage_and_regression_checks_assert_current_UI_is_not_mutated
genuine_blockers: none_requiring_marc; repair_validation_in_progress
next_authorized_step: verify_issue_368_repair_gates_then_recreate_or_revalidate_issue_337_issue_360_phase_1_candidate
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, pull requests, Actions results, issues, frozen releases, and deployment acceptance evidence control whenever they disagree with this file.

## Current verified checkpoint

- Frozen release remains **v3.112** at `1d1759375d37b7de884331c06833de8c727ac5af`. The accepted Azure development demonstration remains on v3.112 and is unchanged.
- `development/salcapa-platform` is now at `d3e3c5626049061171c2db7ff5468a3cfef42178` for the bounded Issue #368 archive/runtime isolation repair.
- The repair changes the historical v3.43 reconstruction and verification tools so their default operation uses an isolated temporary reference directory instead of the current runtime working tree. Existing Docker, CI, CodeQL, and local runtime entrypoints therefore no longer overwrite current governed UI/runtime source when they execute the archived-source commands.
- A regression was added to `tools/check_release_entrypoints.py` that hashes current `static/app.js`, `static/index.html`, and `static/styles.css`, performs the archive reconstruction/verification flow, and fails if any current UI file changes.
- A dedicated `tools/verify_v343_archive.py` helper was added for explicit isolated archive verification.
- GitHub Actions runs for repair head `d3e3c5626049061171c2db7ff5468a3cfef42178` have started and are still pending/validating. No repair acceptance is claimed until the required scoped checks are green.
- The active product milestone remains **Issue #337** with **Issue #360 Phase 1** visible simplification folded into the same coherent visual-refinement milestone.
- Existing controlled validation **PR #365**, `validation/issue-337-light-airy-shell`, remains the historical failed candidate at exact head `2b831b6c0a0df9238d01caeb08c419d257d1710c`. Its prior CI and CodeQL failures were caused by the now-addressed archive/current-runtime coupling. It must not be promoted as-is; after the repair validates, rebuild/rebase or otherwise create a governed exact candidate against the repaired development head and run the required milestone gates.
- There is no current blocker requiring Marc action. The next authorized step is to verify the Issue #368 repair, then recreate/revalidate the Issue #337 / Issue #360 Phase 1 aesthetic candidate and proceed only when the exact candidate artifact is green.

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
