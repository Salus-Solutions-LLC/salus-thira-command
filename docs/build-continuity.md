---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 24 September 2026 22:58 CDT
current_frozen_release: v3.194
current_frozen_commit: 8667fbe7776b7109338d638abf152f40d95f2a7c
active_development_branch: development/salcapa-platform
current_development_head: 9c88ae561d498b53d126863fe1c9ced52f8c276b
active_product_milestone: issue_520_dependable_governed_intake
active_build_system_issue: 520
active_increment: oversize_visibility_v3195_corrected_runtime_identity
last_completed_increment: v3194_oversize_ledger_frozen_identity_mismatch
candidate_release: v3.195
validation_pr: 537
validation_branch: candidate/v3.195-runtime-identity
validation_base: development/salcapa-platform
validation_head: 9c88ae561d498b53d126863fe1c9ced52f8c276b
validation_gate_state: controlled_validation_passed_closed_without_merge
failed_workflows: development_build_continuity_36092448918_stale_record
first_root_failing_gate: stale_candidate_version_in_build_continuity
root_cause: v3194_frozen_runtime_identity_remained_v3193_and_continuity_metadata_was_stale
repair_head: 9c88ae561d498b53d126863fe1c9ced52f8c276b
repair_summary: advance_runtime_identity_to_v3195_and_refresh_continuity_record
genuine_blockers: v3194_superseded_before_publication_release_identity_mismatch_and_v3195_frozen_gate_pending
next_authorized_step: validate_and_freeze_v3195_then_request_release_specific_publication_authorization
deployed_demo_release: v3.193
deployed_demo_state: accepted_runtime_with_v3192_rollback_and_bounded_pending_scan
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Frozen `release/v3.194` at `8667fbe7776b7109338d638abf152f40d95f2a7c` passed source CI but declares runtime version 3.193. Its immutable image publication was not attempted because the protected workflow requires the runtime identity to equal the release branch. Validation PR #537 passed all candidate workflows and closed without merge; exact head `9c88ae561d498b53d126863fe1c9ced52f8c276b` advanced non-force to development with runtime identity 3.195. Accepted v3.193 remains live, v3.192 is its rollback, and the corrected successor awaits development/frozen gates and separate release-specific authorization before image publication. The v3.194 oversize-ledger source change is retained in the successor. Issue #520 still requires enterprise-only routing and live 10,000-file acceptance.

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
