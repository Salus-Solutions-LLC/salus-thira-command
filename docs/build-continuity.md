---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 23 September 2026 13:46 CDT
current_frozen_release: v3.187
current_frozen_commit: 8640677ce4c7180b888ee3682d6e7f90bf048b1c
active_development_branch: development/salcapa-platform
current_development_head: 1e962aa4d51c919a3dfe805ef88edee275837e83
active_product_milestone: issue_370_governed_knowledge_promotion
active_build_system_issue: 370
active_increment: bounded_pending_window_v3188
last_completed_increment: v3187_frozen_live_pending_traversal_limit
candidate_release: v3.188
validation_pr: pending
validation_branch: none
validation_base: development/salcapa-platform
validation_head: 1e962aa4d51c919a3dfe805ef88edee275837e83
validation_gate_state: preflight
failed_workflows: v3.187_live_pending_traversal_limit
first_root_failing_gate: pending_tree_exceeded_twenty_thousand_item_traversal_limit
root_cause: v3.187_abandoned_after_pending_traversal_limit
repair_head: 1e962aa4d51c919a3dfe805ef88edee275837e83
repair_summary: scan_only_five_hundred_pending_files_per_invocation_before_selecting_batch
genuine_blockers: v3.183_through_v3.187_superseded_before_live_acceptance
next_authorized_step: validate_v3188_then_freeze_publish_deploy_and_verify_live_batch
deployed_demo_release: v3.182
deployed_demo_state: accepted_runtime_with_v3181_rollback_and_backlog_stalled_at_traversal_limit
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Frozen v3.180 passed live Microsoft 365 acceptance. The operational diagnostic then counted 549 pending items. Candidate v3.181 processes at most 20 pending items per pass, verifies each item's current parent and ETag before reading, and defers archived extraction retries until the pending backlog is cleared. Accepted v3.180 remains active until the new release passes live acceptance.

Frozen v3.179 passed CI and image publication, but live Microsoft 365 acceptance saw a repeated Graph item during a concurrent folder move. The governed workflow restored accepted v3.178. Candidate v3.180 keeps the bounded continuation traversal and deduplicates valid item IDs; regression checks cover repeated entries, cross-origin links, cycles, and malformed IDs.

Release v3.178 is deployed with v3.176 retained as rollback. A new batch exceeded the single Microsoft Graph folder page and stopped intake before discovery. Candidate v3.179 traverses same-folder continuation pages with a 2,000-item bound and rejects cross-origin or cyclic links. Local pagination tests passed; live verification follows governed validation and deployment.

v3177_superseded_before_publication: Release v3.177 was frozen but its image publication was cancelled before deployment when an identical-content provenance constraint was found. Candidate v3.178 removes that constraint and has a duplicate regression check.\n\nRelease v3.176 at exact commit `12a13fdcb15e62276041553b83dee9699eddf7f4` is the accepted Azure development runtime, with v3.175 retained as rollback. The production image is pinned at `sha256:a420f6a14fb7b296d6cd565483da615f846b94014247a4b43915cfbf5959f430`. CI run `35863059484`, image publication run `35863701593`, and governed deployment run `35864255511` passed. Both pending originals were archived after exact destination verification; the DOCX canonical original matched its archived OneDrive source SHA-256.

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
