---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 13 September 2026 19:22 CDT
current_frozen_release: v3.112
current_frozen_commit: 1d1759375d37b7de884331c06833de8c727ac5af
active_development_branch: development/salcapa-platform
current_development_head: cd481bf16723a750b3a6915c7fbd87282b264eff
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 368
active_increment: issue_368_minimum_A_B_archive_runtime_separation_and_fail_fast_preflight
last_completed_increment: issue_290_authenticated_advisor_decision_checkpoint
candidate_release: none
validation_pr: 365
validation_branch: validation/issue-337-light-airy-shell
validation_base: main
validation_head: 2b831b6c0a0df9238d01caeb08c419d257d1710c
validation_gate_state: failed
failed_workflows: CI; CodeQL Local Analysis
first_root_failing_gate: Reconstruct and verify archived source
root_cause: archived_v3_43_verification_and_reconstruction_are_coupled_to_current_runtime_source
genuine_blockers: issue_368_minimum_A_and_B_repair_required_before_pr_365_rerun_or_replacement
next_authorized_step: complete_issue_368_minimum_A_B_repair_then_revalidate_issue_337_issue_360_phase_1_candidate
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, pull requests, Actions results, issues, frozen releases, and deployment acceptance evidence control whenever they disagree with this file.

## Current verified checkpoint

- Frozen release remains **v3.112** at `1d1759375d37b7de884331c06833de8c727ac5af`. The accepted Azure development demonstration remains on v3.112 and is unchanged.
- `development/salcapa-platform` is currently at `cd481bf16723a750b3a6915c7fbd87282b264eff` (`Record authenticated Advisor decision checkpoint`). The latest relevant CI, CodeQL Local Analysis, Azure infrastructure validation, and other returned workflow families for that exact development head completed successfully.
- The active product milestone is **Issue #337** with **Issue #360 Phase 1** visible simplification folded into the same coherent visual-refinement milestone.
- Open controlled validation **PR #365**, `validation/issue-337-light-airy-shell`, is at exact head `2b831b6c0a0df9238d01caeb08c419d257d1710c`. Its current base is `main`, which Issue #368 identifies as a validation-noise/focused-diff problem to correct under the governed build-system hardening work.
- On that exact validation head, **CI** and **CodeQL Local Analysis** are failed. Both fail at the common **Reconstruct and verify archived source** step before substantive downstream validation can complete.
- **Issue #368** is the immediate prerequisite. Its verified findings show archived v3.43 verification/reconstruction is coupled to current runtime source, and its sequencing requires correction A plus minimum B before rerunning Issue #337 PR #365. Broader focused-diff and validation-efficiency improvements remain governed by the same issue and must not weaken release assurance.
- Therefore the current validation gate state is **failed**. The genuine blocker is the bounded Issue #368 A+B repair. The next authorized step is to complete that repair and then revalidate the exact Issue #337 / Issue #360 Phase 1 candidate. No freeze, release, deployment, or candidate promotion is authorized until the required milestone gates are green on the exact candidate artifact.

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
