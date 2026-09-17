---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 17 September 2026 10:20 CDT
current_frozen_release: v3.124
current_frozen_commit: 602b672828f2f6a1d24fc5b1e32cc36766d79ca8
active_development_branch: development/salcapa-platform
current_development_head: bcfc1b84f72d59bb5acb990fa42852af5fc5309a
active_product_milestone: issue_128_governed_microsoft_365_intake
active_build_system_issue: 370
active_increment: issue_128_v3125_m365_route_release
last_completed_increment: issue_128_v3124_custom_domain_recovery
candidate_release: v3.125
validation_pr: 465
validation_branch: candidate/v3125-m365-route-release
validation_base: main
validation_head: a5689a962a7d3f9b8078eb3bdbd86bd2a5f51966
validation_gate_state: controlled_validation_in_progress
failed_workflows: none
first_root_failing_gate: none
root_cause: fastapi_postponed_local_request_annotation_was_bound_as_query_parameter
repair_head: bcfc1b84f72d59bb5acb990fa42852af5fc5309a
repair_summary: custom_hostname_restored_and_m365_route_binding_repaired
genuine_blockers: none
next_authorized_step: validate_freeze_publish_deploy_and_verify_v3125_m365_read_only_status
deployed_demo_release: v3.124
deployed_demo_state: full_demonstration_accepted
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.124 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `602b672828f2f6a1d24fc5b1e32cc36766d79ca8`; the immutable image is `sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519`. Publication run `35189223604`, deployment run `35190102432`, and live acceptance run `35191132113` passed.
- Live acceptance verified the bounded fictional demonstration, server-controlled role and tenant boundaries, governed journeys, persistence, application-configuration preservation, and temporary-resource cleanup. All 21 validation workflow families passed on exact activation head `b17f418af1532dfe609410ad56085e8d5adfcd91`.
- The v3.124 Microsoft 365 intake connector remains read-only, fixed to the authorized drive and folder, size bounded, rejecting arbitrary item identifiers, and using workload identity without a client secret.
- **Permanent hostname restored:** `salcapa.salus.solutions` now has one SNI binding and an Azure-managed certificate; both the public root and readiness endpoint are healthy. DNS and the deployed v3.124 image were unchanged.
- **v3.125 candidate:** repairs FastAPI binding for the administrator-only Microsoft 365 status and exact-folder listing routes and adds deterministic regression coverage. Tenant-consented Graph access remains least-privilege and read-only; live verification follows deployment.
- **v3.123 is the rollback release** at exact commit `4b976032fe2b8420ca2ec652ae7a7bfc5b130d87` and immutable image `sha256:33b17998643d102b02dc998c409d96f743ec7d5bd8928f05efa999cf8c59b3be`.

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
