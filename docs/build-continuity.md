---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 23 September 2026 08:09 CDT
current_frozen_release: v3.176
current_frozen_commit: 12a13fdcb15e62276041553b83dee9699eddf7f4
active_development_branch: development/salcapa-platform
current_development_head: 6e6f30b23e18b0bdf9f237d0a7dc5cf632cb2f1d
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: knowledge_processing_steady_state_v3176
last_completed_increment: byte_preserving_knowledge_promotion_v3176
candidate_release: none
validation_pr: none
validation_branch: none
validation_base: development/salcapa-platform
validation_head: 12a13fdcb15e62276041553b83dee9699eddf7f4
validation_gate_state: all_required_gates_green
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: none
genuine_blockers: none
next_authorized_step: monitor_automatic_knowledge_processing
deployed_demo_release: v3.176
deployed_demo_state: accepted_stable_runtime_with_v3175_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.176 at exact commit `12a13fdcb15e62276041553b83dee9699eddf7f4` is the accepted Azure development runtime, with v3.175 retained as rollback. The production image is pinned at `sha256:a420f6a14fb7b296d6cd565483da615f846b94014247a4b43915cfbf5959f430`. CI run `35863059484`, image publication run `35863701593`, and governed deployment run `35864255511` passed. Both pending originals were archived after exact destination verification; the DOCX canonical original matched its archived OneDrive source SHA-256.

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
