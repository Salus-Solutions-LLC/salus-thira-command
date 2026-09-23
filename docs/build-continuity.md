---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 23 September 2026 07:50 CDT
current_frozen_release: v3.175
current_frozen_commit: 62b3fbc5089b237ee6aee044de84ace699b08d66
active_development_branch: development/salcapa-platform
current_development_head: 907d2c2f59c4c2d41e3687f9356f8663e8075602
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: byte_preserving_knowledge_promotion_v3176
last_completed_increment: verified_knowledge_destination_write_v3175
candidate_release: v3.176
validation_pr: pending
validation_branch: release/v3.176
validation_base: development/salcapa-platform
validation_head: 907d2c2f59c4c2d41e3687f9356f8663e8075602
validation_gate_state: repair_validation_pending
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: none
genuine_blockers: v3176_full_validation_pending
next_authorized_step: validate_freeze_publish_and_deploy_v3176
deployed_demo_release: v3.175
deployed_demo_state: accepted_stable_runtime_with_v3174_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.175 at exact commit `62b3fbc5089b237ee6aee044de84ace699b08d66` is the accepted Azure development runtime, with v3.174 retained as rollback. Release v3.176 is the controlled candidate for byte-preserving Office originals. The scoped Graph grants now allow PDF promotion and archiving. Verify the full candidate, freeze the exact all-green commit, publish an immutable image, then deploy via governed activation records.

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
