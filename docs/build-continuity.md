---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 23 September 2026 08:09 CDT
current_frozen_release: v3.176
current_frozen_commit: 12a13fdcb15e62276041553b83dee9699eddf7f4
active_development_branch: development/salcapa-platform
current_development_head: 21a4ce9c1d8e62743f9fd8c545285dea49e8eabd
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: protection_advisor_knowledge_visibility_and_duplicate_safe_intake_v3178
last_completed_increment: byte_preserving_knowledge_promotion_v3176
candidate_release: v3.178
validation_pr: none
validation_branch: none
validation_base: development/salcapa-platform
validation_head: 12a13fdcb15e62276041553b83dee9699eddf7f4
validation_gate_state: preflight
failed_workflows: v3.177_image_publication_cancelled_and_v3.178_build_continuity
first_root_failing_gate: identical_content_provenance
root_cause: v3.177_abandoned_before_publication_after_identical_content_provenance_gap
repair_head: 85afad2128f1c05a9d277627860bc30421d9032a
repair_summary: nonunique_sha_lookup_preserves_every_source_and_duplicate_regression_passes
genuine_blockers: none
next_authorized_step: validate_v3178_candidate_then_freeze_and_publish
deployed_demo_release: v3.176
deployed_demo_state: accepted_stable_runtime_with_v3175_rollback
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Release v3.177 was frozen but its image publication was cancelled before deployment when an identical-content provenance constraint was found. Candidate v3.178 removes that constraint and has a duplicate regression check.\n\nRelease v3.176 at exact commit `12a13fdcb15e62276041553b83dee9699eddf7f4` is the accepted Azure development runtime, with v3.175 retained as rollback. The production image is pinned at `sha256:a420f6a14fb7b296d6cd565483da615f846b94014247a4b43915cfbf5959f430`. CI run `35863059484`, image publication run `35863701593`, and governed deployment run `35864255511` passed. Both pending originals were archived after exact destination verification; the DOCX canonical original matched its archived OneDrive source SHA-256.

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
