---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 14 September 2026 22:16 CDT
current_frozen_release: v3.113
current_frozen_commit: 9d9873203fffd8c8ae477123ea94eb35b27c2acd
active_development_branch: development/salcapa-platform
current_development_head: 1e21b4f1eeab012c67a2157c68dd8f43c269afa8
active_product_milestone: issue_360_phase_2
active_build_system_issue: 370
active_increment: issue_360_phase_2_task_oriented_navigation
last_completed_increment: issue_360_phase_2_task_oriented_navigation
candidate_release: none
validation_pr: 378
validation_branch: candidate/issue-360-phase2-task-navigation-20260914
validation_base: development/salcapa-platform
validation_head: 1e21b4f1eeab012c67a2157c68dd8f43c269afa8
validation_gate_state: controlled_validation_passed_closed_without_merge
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: task_oriented_navigation_and_progressive_disclosure_validated
genuine_blockers: none
next_authorized_step: continue_issue_360_phase_2_one_page_one_job_simplification_with_issue_368_focused_validation_and_issue_369_lean_controls
deployed_demo_release: v3.113
deployed_demo_state: full_demonstration_acceptance
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.113 is frozen** at exact commit `9d9873203fffd8c8ae477123ea94eb35b27c2acd` on `release/v3.113`; controlled validation PR #373 passed all 20 required workflow families and closed without merge.
- [Immutable-image publication workflow 34908424307](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34908424307) published that exact frozen source as `salcapadevb48224acr.azurecr.io/salcapa@sha256:84fe4ca875ec1d8478aa617fcd873adcf62c5eba78134ea4575de8471bfd9eb8` on 14 September 2026 at 18:22 CDT.
- [Governed application-deployment workflow 34915370013](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34915370013) deployed exact frozen v3.113 and that immutable digest on 14 September 2026 at 20:03 CDT. Image, workload identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, readiness, dependency, and sign-in checks passed; rollback was not invoked.
- [Live demonstration acceptance workflow 34921297674](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34921297674) passed on 14 September 2026 at 21:31 CDT. Aster Ridge, Cedar Vale, and Northstar, 24 fictional personas, tenant and role boundaries, ordinary read-only evaluator access, cross-tenant denial, PostgreSQL persistence, and SalINTEL/SalTHIRA/SalCAPA/SalOPS/PROVE journeys were verified. The temporary job was removed and the deployed application configuration remained unchanged.
- Exact accepted v3.112 remains available as the verified rollback baseline.
- The deployment remains passwordless, bounded to the existing approved Azure development environment, and prohibited from changing custom DNS or performing a public production cutover.
- Issue #368 archive/current-runtime separation remains preserved in frozen v3.113: immutable v3.43 evidence verification cannot overwrite the current interface.
- [Controlled validation PR #378](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/378) closed without merge after exact commit `1e21b4f1eeab012c67a2157c68dd8f43c269afa8` passed the path-scoped CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 14 September 2026 at 22:16 CDT.
- Issue #360 Phase 2 now keeps Command Center and Common Operating Picture visible as the two starting choices while progressively disclosing reports, intelligence, risk, and operations. Specialist views reveal their active work area; access, tenancy, disclosure, human-authority, date/time, and release controls remain unchanged.

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
