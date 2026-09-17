---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 17 September 2026 02:10 CDT
current_frozen_release: v3.124
current_frozen_commit: 602b672828f2f6a1d24fc5b1e32cc36766d79ca8
active_development_branch: development/salcapa-platform
current_development_head: 65ab7854c10dae50dd28440908525f56019e1948
active_product_milestone: issue_128_governed_microsoft_365_intake
active_build_system_issue: 370
active_increment: issue_128_v3124_live_evaluator_acceptance
last_completed_increment: issue_128_v3124_application_promotion
candidate_release: v3.124
validation_pr: 457
validation_branch: release-activation/v3.124-live-acceptance
validation_base: main
validation_head: eb409f06a41d361c026470ea20761a27c2715a6c
validation_gate_state: controlled_validation_in_progress
failed_workflows: none
first_root_failing_gate: none
root_cause: exact_v3124_deployment_passed_and_requires_separate_live_acceptance
repair_head: e66291c1b744afec0f1d10fc7c6d113ec5ee9673
repair_summary: activate_bounded_v3124_live_demonstration_acceptance
genuine_blockers: v3124_live_acceptance_not_yet_executed
next_authorized_step: validate_activation_then_close_pr_without_merge_and_fast_forward_development_to_trigger_live_acceptance
deployed_demo_release: v3.123
deployed_demo_state: full_demonstration_accepted
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.124 is frozen, published, and deployed, and is awaiting its separate live demonstration acceptance.** Frozen source is exact commit `602b672828f2f6a1d24fc5b1e32cc36766d79ca8`; the immutable image is `sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519`. Publication run `35189223604` and deployment run `35190102432` passed.
- The v3.124 capability is a least-privilege Microsoft 365 intake connector: read-only, fixed to the authorized drive and folder, size bounded, rejecting arbitrary item identifiers, and preserving metadata/content length agreement. Administrative status and listing use existing administrator authorization. Workload identity is used without a client secret.
- **v3.123 remains the accepted stable demonstration and rollback release** at exact commit `4b976032fe2b8420ca2ec652ae7a7bfc5b130d87` and immutable image `sha256:33b17998643d102b02dc998c409d96f743ec7d5bd8928f05efa999cf8c59b3be`. Publication run `35185662854`, deployment run `35186525899`, and live acceptance run `35187593491` passed.
- The current activation runs only the bounded fictional-data v3.124 live evaluator and preserves deployed application configuration. It does not broaden Microsoft 365 scope, add write authority, publish reports, change DNS, or authorize production cutover.

## Source precedence

1. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.
2. This continuity record after comparison with those GitHub records.
3. Approved architecture and doctrine records referenced by the active milestone.
4. Conversation history only as supporting design context.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

1. Compare this record with the exact development head, open validation pull requests, frozen releases, activation records, and relevant Actions results.
2. Record the exact candidate PR/head, base, gate state, and first/root failing gate.
3. Preserve the distinction among current development, frozen release, published immutable image, deployed runtime, accepted stable release, and rollback baseline.
4. After every required gate is green, close the controlled validation pull request without merge, then advance only the exact verified head through a non-force fast-forward.
5. A failed or inconsistent gate fails closed. Never weaken a security, privacy, accessibility, abuse, recovery, rollback, identity, tenant, disclosure, provenance, or human-authority control to make a release pass.

## Standing controls

- Preserve `main`, `development/v1.17`, `release/v1.16`, every frozen release, and all accepted deployment evidence.
- Human-First Communications and Human Trust & Comprehension doctrine remain in force.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.
- Keep Microsoft Graph access least-privilege, read-only, exact-folder scoped, auditable, revocable, and separately governed from report publication or other write paths.
