---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 17 September 2026 01:00 CDT
current_frozen_release: v3.123
current_frozen_commit: 4b976032fe2b8420ca2ec652ae7a7bfc5b130d87
active_development_branch: development/salcapa-platform
current_development_head: 159e76945944466d4454c66eaed487b63396a54d
active_product_milestone: issue_128_governed_microsoft_365_intake
active_build_system_issue: 370
active_increment: issue_128_v3124_governed_m365_intake
last_completed_increment: issue_290_v3123_controlled_deployment_and_live_acceptance
candidate_release: v3.124
validation_pr: 454
validation_branch: development/governed-m365-v3124-final
validation_base: main
validation_head: pending
validation_gate_state: github_validation_running
failed_workflows: none
first_root_failing_gate: none
root_cause: v3123_is_accepted_and_m365_connector_requires_distinct_successor_release
repair_head: fd0cada3baf422f9e4968c7189c05b22ecf561b1
repair_summary: reconcile_v3123_acceptance_and_advance_read_only_m365_connector_to_v3124
genuine_blockers: none
next_authorized_step: validate_exact_v3124_candidate_then_close_pr_without_merge_and_fast_forward_development
deployed_demo_release: v3.123
deployed_demo_state: full_demonstration_accepted
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.123 is frozen, deployed, and accepted** at exact commit `4b976032fe2b8420ca2ec652ae7a7bfc5b130d87` on `release/v3.123`.
- [Immutable-image publication run 35185662854](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35185662854) published `salcapadevb48224acr.azurecr.io/salcapa@sha256:33b17998643d102b02dc998c409d96f743ec7d5bd8928f05efa999cf8c59b3be`.
- [Governed deployment run 35186525899](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35186525899) deployed that exact image. Workload identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, dependencies, readiness, and sign-in verification passed.
- [Live acceptance run 35187593491](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35187593491) verified Aster Ridge, Cedar Vale, and Northstar, 24 fictional personas, server-controlled tenant and role boundaries, cross-tenant denial, governed SalINTEL/SalTHIRA/SalCAPA/SalOPS/PROVE journeys, persistence, application-configuration preservation, and temporary-job cleanup.
- Exact accepted **v3.122** commit `e84e19d77cef1b39d605260ae2fbe836e95888e4` and image `sha256:7088640e7b42a2005f01000f04bf004b241e7e045b11414adbdb53d725f65ef9` remain the rollback baseline.
- **v3.124 is the distinct candidate** for the least-privilege Microsoft 365 connector. It is read-only, exact-folder scoped, size bounded, rejects arbitrary item identifiers, preserves source metadata and content-length checks, and exposes status and file listing only through existing administrator authorization.
- v3.124 uses the Azure workload identity to obtain an assertion and exchanges it through the existing Microsoft Entra application for Microsoft Graph `.default` authority. No client secret is added.
- Frozen v3.123 remains immutable. The connector does not broaden folder scope, create Microsoft 365 write authority, publish reports, change DNS, or authorize production cutover.

## Authoritative connector boundary

The v3.124 candidate is fixed to the already authorized Microsoft 365 application, OneDrive drive, and SalCAPA Intake folder recorded in the governed Azure parameters. These identifiers are configuration, not credentials. No arbitrary drive, folder, site, or item value is accepted from a request.

Current candidate verification includes Python compilation, deterministic connector smoke tests, Azure Bicep compilation, deployment-policy validation, production-container tests, PostgreSQL tests, CodeQL, Public Protection Advisor, recovery, rollback, accessibility, privacy, security, abuse resistance, and the capability-specific suites.

## Source precedence

1. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.
2. This continuity record after comparison with those GitHub records.
3. Approved architecture and doctrine records referenced by the active milestone.
4. Conversation history only as supporting design context.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

1. Compare this record with the exact development head, open validation pull requests, frozen release branches, activation records, and relevant Actions results.
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
