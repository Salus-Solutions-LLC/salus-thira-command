---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 24 September 2026 23:26 CDT
current_frozen_release: v3.195
current_frozen_commit: 9c88ae561d498b53d126863fe1c9ced52f8c276b
active_development_branch: development/salcapa-platform
current_development_head: d713345b90125b88ea5be303cf8599f394e2c000
active_product_milestone: issue_520_dependable_governed_intake
active_build_system_issue: 520
active_increment: oversize_visibility_v3195_application_promotion
last_completed_increment: v3195_accepted_immutable_image_and_governed_deployment
candidate_release: v3.195
validation_pr: 537
validation_branch: candidate/v3.195-runtime-identity
validation_base: development/salcapa-platform
validation_head: 9c88ae561d498b53d126863fe1c9ced52f8c276b
validation_gate_state: all_required_gates_green
failed_workflows: none
first_root_failing_gate: none
root_cause: v3194_release_identity_mismatch_corrected_in_v3195
repair_head: 9c88ae561d498b53d126863fe1c9ced52f8c276b
repair_summary: v3195_runtime_identity_and_immutable_image_live_verified
genuine_blockers: issue_520_complete_nested_drain_and_member_routing_not_accepted
next_authorized_step: verify_enterprise_ownership_then_route_bulk_worker_and_complete_issue_520_acceptance
deployed_demo_release: v3.195
deployed_demo_state: accepted_immutable_runtime_with_v3193_rollback_and_bounded_oversize_holds
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

Accepted v3.195 is frozen at `9c88ae561d498b53d126863fe1c9ced52f8c276b`, published at immutable digest `sha256:035ef8684d2092fc6eb1f2b51769c6e7e30b443b2e28dd571e6edecf54b32ecd`, and passed governed Azure deployment run `36093814271` with v3.193 retained as rollback. The scheduled worker observed 20 discovered files, five promotions, 34 retry-required records, three oversized holds, and zero exception reviews. This accepted bounded pass does not complete issue #520's fair 10,000-file nested drain, ZIP/member routing, or recovery acceptance. The empty `20 Salus Enterprise Knowledge` folder inside `10 Pending Classification` has item ID `01DBTAFUOMR2BU2SRKGBAY3INJKHT6TB74`; it is not enabled as a bulk route and holds no source files. Frozen v3.194 was superseded before publication because its runtime marker was 3.193. Exact frozen branches and workflow results remain authoritative.

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
