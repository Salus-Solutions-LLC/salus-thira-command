---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 22 September 2026 14:05 CDT
current_frozen_release: v3.162
current_frozen_commit: 731d2b320d0f237562a5ef5ecd9cee3d86a31dd9
active_development_branch: development/salcapa-platform
current_development_head: 14325f63ad7d3de513c53fe1b624d405b0c89f91
active_product_milestone: issue_370_governed_document_ingestion
active_build_system_issue: 370
active_increment: protection_advisor_v3163_secure_report_download
last_completed_increment: protection_advisor_v3162_professional_report
candidate_release: v3.163
validation_pr: 514
validation_branch: release/v3.163
validation_base: development/salcapa-platform
validation_head: 14325f63ad7d3de513c53fe1b624d405b0c89f91
validation_gate_state: preflight
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: 499da6d404bf261ffa09f5bd63a37ac3526fd9e4
repair_summary: protection_advisor_csrf_authenticated_pdf_download
genuine_blockers: deployment_continuity_superseded_pending_v3163_validation
next_authorized_step: freeze_publish_and_deploy_v3163
deployed_demo_release: v3.162
deployed_demo_state: accepted_stable_runtime_with_v3161_rollback
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
