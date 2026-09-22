---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 22 September 2026 13:08 CDT
current_frozen_release: v3.161
current_frozen_commit: f48b80fd5ca026969949b64155ecb42a487aafa9
active_development_branch: development/salcapa-platform
current_development_head: 862d87a969e44377d5648ed5abf17839ffc3aed9
active_product_milestone: issue_370_governed_document_ingestion
active_build_system_issue: 370
active_increment: protection_advisor_v3162_professional_report
last_completed_increment: protection_advisor_v3161_footer_image_relationships
candidate_release: v3.162
validation_pr: 514
validation_branch: release/v3.162
validation_base: development/salcapa-platform
validation_head: 862d87a969e44377d5648ed5abf17839ffc3aed9
validation_gate_state: preflight
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: b8620a18bff65af4c305ce82b1668807ae20d7d5
repair_summary: protection_advisor_professional_report_renderer_and_smoke_validation
genuine_blockers: deployment_continuity_superseded_pending_v3162_validation
next_authorized_step: freeze_publish_and_deploy_v3162
deployed_demo_release: v3.161
deployed_demo_state: accepted_stable_runtime_with_v3160_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.161 at exact commit `f48b80fd5ca026969949b64155ecb42a487aafa9` is the accepted runtime and rollback baseline. Release v3.162 is the controlled Protection Advisor professional-report candidate. Freeze only the exact all-green candidate commit as `release/v3.162`, publish its immutable image, and deploy it through the governed activation records.

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
