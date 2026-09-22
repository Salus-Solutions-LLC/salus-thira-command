---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 22 September 2026 18:20 CDT
current_frozen_release: v3.166
current_frozen_commit: 1afbd4679317a91781c1c3f249570d64c07b19e5
active_development_branch: development/salcapa-platform
current_development_head: 1985cd4fa3214bf9e1c215123902dc11b47b21cd
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: risk_based_automatic_knowledge_promotion_v3167
last_completed_increment: processed_intake_archive_v3166
candidate_release: v3.167
validation_pr: pending
validation_branch: release/v3.167
validation_base: development/salcapa-platform
validation_head: 1985cd4fa3214bf9e1c215123902dc11b47b21cd
validation_gate_state: repair_validation_pending
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: none
genuine_blockers: v3167_full_validation_pending
next_authorized_step: validate_freeze_publish_and_deploy_v3167
deployed_demo_release: v3.166
deployed_demo_state: accepted_stable_runtime_with_v3165_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.166 at exact commit `1afbd4679317a91781c1c3f249570d64c07b19e5` is the accepted runtime, with v3.165 retained as the rollback baseline. Release v3.167 is the controlled risk-based automatic knowledge-promotion candidate. Freeze only the exact all-green candidate commit as `release/v3.167`, publish its immutable image, and deploy it through the governed activation records.

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
