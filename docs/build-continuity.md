---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 19:16 CDT
current_frozen_release: v3.113
current_frozen_commit: 9d9873203fffd8c8ae477123ea94eb35b27c2acd
active_development_branch: development/salcapa-platform
current_development_head: 549dfea9b777ce02a6d26f310078b1265389b770
active_product_milestone: issue_337_with_issue_360_phase_1
active_build_system_issue: 370
active_increment: issue_337_v3113_application_promotion
last_completed_increment: issue_337_v3113_immutable_image_published
candidate_release: v3.113
validation_pr: 375
validation_branch: candidate/v3.113-application-activation
validation_base: main
validation_head: pending_exact_final_head_after_continuity_commit
validation_gate_state: controlled_validation_in_progress
failed_workflows: pending
first_root_failing_gate: pending
root_cause: pending_validation
repair_head: none
repair_summary: exact_application_and_rollback_bindings_advanced_to_v3113_and_accepted_v3112
genuine_blockers: v3113_application_not_yet_promoted
next_authorized_step: complete_PR_375_exact_validation_close_without_merge_advance_exact_green_head_to_development_trigger_protected_application_deployment_capture_live_result_then_run_three_environment_acceptance
deployed_demo_release: v3.112
deployed_demo_state: accepted_unchanged
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.113 is frozen** at exact commit `9d9873203fffd8c8ae477123ea94eb35b27c2acd` on `release/v3.113`; controlled validation PR #373 passed all 20 required workflow families and closed without merge.
- [Immutable-image publication workflow 34908424307](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34908424307) published that exact frozen source as `salcapadevb48224acr.azurecr.io/salcapa@sha256:84fe4ca875ec1d8478aa617fcd873adcf62c5eba78134ea4575de8471bfd9eb8` on 14 September 2026 at 18:22 CDT. Frozen-source identity, runtime release identity, non-root execution, workload identity, scoped registry authority, and immutable labels passed; no application, traffic, DNS, database, mutable tag, or public-production state changed.
- The accepted Azure development demonstration remains exact v3.112 at commit `1d1759375d37b7de884331c06833de8c727ac5af` and digest `sha256:605822c4f48a82ac9823a2f80e846c0cc6b9ac944afe20c95240cae854e549ce`.
- [Controlled validation PR #375](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/375) governs only the v3.113 application promotion. The activation, deployment workflow, validation contract, preflight evidence, and demonstration continuity bind exact v3.113 while retaining accepted v3.112 as the fail-closed rollback target.
- The application deployment remains passwordless, bounded to the existing approved Azure development environment, and prohibited from changing custom DNS or performing a public production cutover.
- Issue #368 archive/current-runtime separation remains preserved in frozen v3.113: immutable v3.43 evidence verification cannot overwrite the current interface.

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
