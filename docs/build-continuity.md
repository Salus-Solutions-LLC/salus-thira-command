---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 22 September 2026 17:05 CDT
current_frozen_release: v3.163
current_frozen_commit: 71102b0091a18b790a02b7e30997f5a2e3dea146
active_development_branch: development/salcapa-platform
current_development_head: 69742409f713d0e090a77df2758f91b595a399d3
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: knowledge_promotion_v3165
last_completed_increment: protection_advisor_v3163_secure_report_download
candidate_release: v3.165
validation_pr: pending
validation_branch: release/v3.165
validation_base: development/salcapa-platform
validation_head: 69742409f713d0e090a77df2758f91b595a399d3
validation_gate_state: repair_validation_pending
failed_workflows: immutable_image_publication_and_build_continuity
first_root_failing_gate: frozen_runtime_release_identity
root_cause: v3.164_abandoned_before_image_publication_after_release_identity_mismatch
repair_head: 69742409f713d0e090a77df2758f91b595a399d3
repair_summary: align_version_runtime_and_record_single_abandoned_candidate_gap
genuine_blockers: v3165_full_validation_pending
next_authorized_step: validate_freeze_publish_and_deploy_v3165
deployed_demo_release: v3.163
deployed_demo_state: accepted_stable_runtime_with_v3162_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.162 at exact commit `731d2b320d0f237562a5ef5ecd9cee3d86a31dd9` is the accepted runtime and rollback baseline. Release v3.163 is the controlled Protection Advisor secure professional-report download candidate. Freeze only the exact all-green candidate commit as `release/v3.163`, publish its immutable image, and deploy it through the governed activation records.

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
