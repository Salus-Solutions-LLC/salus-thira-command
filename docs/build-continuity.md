---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 21 September 2026 18:30 CDT
current_frozen_release: v3.155
current_frozen_commit: 1a3cc437971aa10600d22885727158ad7fac35c8
active_development_branch: development/salcapa-platform
current_development_head: 1a3cc437971aa10600d22885727158ad7fac35c8
active_product_milestone: issue_370_governed_document_ingestion
active_build_system_issue: 370
active_increment: protection_advisor_v3155_https_sso
last_completed_increment: protection_advisor_v3154_report_contract_compatibility
candidate_release: v3.156
validation_pr: 514
validation_branch: release/v3.156
validation_base: development/salcapa-platform
validation_head: a743f6c43bd2624bf4a266cd07d337800df23682
validation_gate_state: preflight
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: 1a3cc437971aa10600d22885727158ad7fac35c8
repair_summary: protection_advisor_https_sso_target
genuine_blockers: deployment_continuity_superseded_pending_v3156_validation
next_authorized_step: validate_publish_and_deploy_v3155
deployed_demo_release: v3.150
deployed_demo_state: protection_advisor_anonymous_review_button_repaired_live_verified_and_nested_m365_acceptance_passed_with_temporary_job_deleted
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.153 is the current frozen release at exact commit `a0fc3244203e51ad524683fb7e63868de876f4ce`. Release v3.154 is the controlled validation candidate for the Protection Advisor report-contract compatibility repair. Pull request 514 validates `validation/v3.154` against `development/salcapa-platform` and must be closed without merge after all required gates pass.

## Source precedence

GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records. Those records control whenever they disagree with this file.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

Compare this record with the exact development head, controlled validation pull request, frozen release, activation records, and relevant Actions results.

Preserve the distinction among current development, frozen release, published immutable image, deployed runtime, accepted stable release, and rollback baseline.

After every required gate is green, close the controlled validation pull request without merge, then advance only the exact verified head through a non-force fast-forward.

A failed or inconsistent gate fails closed. Never weaken a security, privacy, accessibility, abuse, recovery, rollback, identity, tenant, disclosure, provenance, or human-authority control to make a release pass.

## Standing controls

Human-First Communications and Human Trust & Comprehension doctrine remain in force.

Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.

Keep Microsoft Graph access least-privilege, exact-folder scoped, auditable, revocable, and separately governed from report publication or other write paths.
