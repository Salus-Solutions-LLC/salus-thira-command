---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 15 September 2026 11:16 CDT
current_frozen_release: v3.113
current_frozen_commit: 9d9873203fffd8c8ae477123ea94eb35b27c2acd
active_development_branch: development/salcapa-platform
current_development_head: 7f1867ab28245dcda7f1f1263823e4b76e4e8113
active_product_milestone: issue_360_phase_3
active_build_system_issue: 370
active_increment: issue_360_phase_3_decision_source_reference_reuse
last_completed_increment: issue_360_phase_3_decision_source_reference_reuse
candidate_release: none
validation_pr: 400
validation_branch: candidate/issue-360-phase3-decision-source-reuse-20260915
validation_base: development/salcapa-platform
validation_head: 7f1867ab28245dcda7f1f1263823e4b76e4e8113
validation_gate_state: controlled_validation_passed_closed_without_merge
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: governed_decision_source_reference_reuse_validated
genuine_blockers: none
next_authorized_step: continue_issue_360_phase_3_enter_once_reuse_by_governed_reference_with_issue_368_focused_validation_and_issue_369_lean_controls
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
- [Controlled validation PR #380](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/380) closed without merge after exact commit `b412c0eafbbe09ac47dec69bbc56122f15639348` passed the focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 14 September 2026 at 22:32 CDT.
- The Reports page now follows one governed job: prepare a report for authorized review. Needs Your Attention, Current Work, immutable version status, hashes, authority, and next steps remain visible; preview/export and supporting assessment detail use progressive disclosure and explicitly do not approve or release a report.
- [Controlled validation PR #381](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/381) closed without merge after all 43 governed checks passed on exact continuity commit `84ebe99371253a5e5305d3f429ebcb606a15e3e9`; that exact commit advanced by non-force fast-forward on 15 September 2026 at 01:00 CDT.
- [Controlled validation PR #382](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/382) closed without merge after exact commit `1670abbe6a88d502ad51076cb4a11e16b22c7c79` passed focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 01:10 CDT.
- The SalINTEL overview now separates non-closed incoming information under Needs Your Attention from the intelligence register under Current Work. New finding entry and closed observation history use progressive disclosure; unverified-information separation, qualification, tenant access, provenance, human authority, and the SalINTEL-to-SalTHIRA handoff remain unchanged.
- [Controlled validation PR #384](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/384) closed without merge after exact commit `66007dccb0be3028b9240e05bacf729b7fc3108e` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 02:32 CDT.
- The Protected Member SalOPS overview now keeps the support request as its primary first-use action, shows estimate decisions under Needs Your Attention, keeps requests and active engagements under Current Work, and progressively discloses service, expert, financial, statement, and field-update detail. It explicitly does not create an invoice or operational authority.
- [Controlled validation PR #386](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/386) closed without merge after exact commit `71d27516adb9351e5a6be09d000ac5ef8e55eb0e` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 03:11 CDT.
- The SalTHIRA assessment overview now distinguishes risk-assessment workspaces, reassessment lifecycle items needing attention, and assessment creation or editing. SalTHIRA remains an evidence-based risk and priority method; authorized people retain assessment, decision, approval, and operational authority.
- [Controlled validation PR #388](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/388) closed without merge after exact commit `659d8bae691e17c0ef691a20e83818b112db08ee` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 04:11 CDT.
- The Protected Member SalINTEL overview now keeps governed observation reporting as the primary task, shows open observation records under Current Work, and progressively discloses qualified intelligence and closed history. It states that Salus personnel review submitted information before qualification or routing and that submission does not establish a finding, decision, or operational action.
- [Controlled validation PR #390](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/390) closed without merge after exact commit `79afe259b53cda80b9c1faaf4c9fa7971a6582e9` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 05:12 CDT.
- The Common Operating Picture now leads with assessment lifecycle items needing attention, keeps qualified intelligence and active protective work under Current Picture, and progressively discloses accepted risk, released work, and observations. It presents saved information and evidence while authorized people retain priority, approval, and operational authority.
- Issue #360 Phase 2 task-oriented simplification is now represented across the six primary navigation surfaces: Command Center, Common Operating Picture, Reports, Intelligence Overview, Risk Assessments, and Operations & Requests. The next bounded work begins Phase 3 governed information reuse; this is not a release freeze or Azure promotion checkpoint.
- [Controlled validation PR #392](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/392) closed without merge after exact commit `abdc371226f7c5a48439efbb33058721ee78650d` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL checks. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 06:09 CDT.
- New coordination threads now reuse the selected active assessment by governed reference instead of asking people to re-enter its number. The interface explains how to change that context and preserves workspace-level threads when no assessment is selected; existing server-side assessment access and tenant validation remain authoritative.
- [Implementation PR #396](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/396) advanced development to exact commit `eae1847a433b622152a3177c084c2af3e5ef3a83` after [controlled validation PR #397](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/397) passed all 43 governed checks and closed without merge. The additive presentation repair aligns the application with the Salus Solutions visual language, establishes readable typography floors, preserves explicit process indicators, and changes no authentication, authorization, tenant, disclosure, records, or frozen-release control.
- [Controlled validation PR #398](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/398) closed without merge after exact commit `ea6282bc81a6ab3cadcd555cc15bcfa7f82d6f74` passed all seven focused CI, PostgreSQL 16, production-container, contextual-intake, and local CodeQL jobs. The exact green commit advanced by non-force fast-forward on 15 September 2026 at 10:08 CDT; stale predecessor PR #394 closed without merge as superseded.
- Observation routing now reuses the selected active assessment by governed reference instead of asking personnel to re-enter an assessment number. SalTHIRA or SalOPS routing fails closed with clear guidance when no assessment is active; server-side routing, assessment access, tenant, disclosure, provenance, and human-authority controls remain authoritative.

- [Controlled validation PR #400](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/400) closed without merge after exact commit `7f1867ab28245dcda7f1f1263823e4b76e4e8113` passed all seven focused checks. Decision requests now start from the exact governed intelligence, reassessment, accepted-risk, or operations record visible in the Common Operating Picture, reusing its server identity and title instead of asking personnel to re-enter internal source identifiers. Server-side tenant, accessible-assessment, source-state, action compatibility, duplicate-request, disclosure, and human-authority controls remain authoritative.

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
