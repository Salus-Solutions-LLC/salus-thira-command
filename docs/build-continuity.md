---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 20 September 2026 10:45 CDT
current_frozen_release: v3.148
current_frozen_commit: ba0cab61717b8ccf897069b557de9a891bde69f4
active_development_branch: development/salcapa-platform
current_development_head: pending
active_product_milestone: issue_370_governed_document_ingestion
active_build_system_issue: 370
active_increment: protection_advisor_v3149_responsive_embed_and_print_results
last_completed_increment: issue_370_v3148_human_review_indexing_and_evidence_routing_workspace_live_acceptance
candidate_release: v3.149
validation_pr: none
validation_branch: release/v3.149
validation_base: development/salcapa-platform
validation_head: pending
validation_gate_state: github_validation_running
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: none
repair_summary: responsive_wix_embed_and_printable_part1_part2_results
genuine_blockers: none
next_authorized_step: validate_in_wix_freeze_publish_deploy_and_live_accept_v3149
deployed_demo_release: v3.148
deployed_demo_state: governed_review_indexing_routing_and_nested_m365_live_acceptance_passed_and_temporary_job_deleted
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records control whenever they disagree with this file.

## Current verified checkpoint

- **v3.124 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `602b672828f2f6a1d24fc5b1e32cc36766d79ca8`; the immutable image is `sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519`. Publication run `35189223604`, deployment run `35190102432`, and live acceptance run `35191132113` passed.
- Live acceptance verified the bounded fictional demonstration, server-controlled role and tenant boundaries, governed journeys, persistence, application-configuration preservation, and temporary-resource cleanup. All 21 validation workflow families passed on exact activation head `b17f418af1532dfe609410ad56085e8d5adfcd91`.
- The v3.124 Microsoft 365 intake connector remains read-only, fixed to the authorized drive and folder, size bounded, rejecting arbitrary item identifiers, and using workload identity without a client secret.
- **Permanent hostname restored:** `salcapa.salus.solutions` now has one SNI binding and an Azure-managed certificate; both the public root and readiness endpoint are healthy. DNS and the deployed v3.124 image were unchanged.
- **v3.125 is frozen but was superseded before image publication.** It repairs FastAPI binding for the administrator-only Microsoft 365 status and exact-folder listing routes; those changes carry forward into v3.126. Tenant-consented Graph access remains least-privilege and read-only.
- **v3.127 is frozen, published, deployed, and live accepted.** It preserves the permanent OIDC callback and custom hostname, keeps Wix authoritative for the Protection Advisor shell, redirects the legacy application route to the canonical Wix page, and preserves the dedicated embed surface. All governed deployment and live identity checks passed.
- **v3.128 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `5fbd01ab2dc34179a44c8f4fef94bcc4054c4123`; the immutable image is `sha256:81b0fa2f1419a6c72ff5891aad81633dae08d640f63f928546189d473fe2a194`. It replaces the expanding assessment with a bounded one-question-at-a-time flow.
- **v3.129 is frozen, published, deployed, and live accepted.** It resets the embedded document to its own top after assessment start and every question transition so later questions are not clipped inside the Wix iframe.
- **v3.130 is frozen, published, deployed, and live accepted.** It removes the duplicate visible Protection Advisor title from the embedded document while retaining an accessible hidden heading and the authoritative Wix title.
- **v3.131 is frozen, published, deployed, and live accepted.** It makes the fixed workspace sidebar independently scrollable and presents the session action as the orange `< Sign Out` control.
- **v3.136 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `0eee07661658f229544317670c635568ce649bef`; the immutable image is `sha256:e7a1a14af003806fa19875cb6ce13cef9e51c6c1f48338939ef7b174e39bc3a9`. Live OneDrive/SharePoint intake acceptance passed and the temporary Azure test job was deleted and verified absent.
- **v3.148 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `ba0cab61717b8ccf897069b557de9a891bde69f4`; immutable image `sha256:7a3ca46743716e3a9e25cb2547eb2ae2c488dfa595f5268cde253c739c79229d`. Publication run `35518188644` and governed deployment/live acceptance run `35518422910` passed. Human-reviewed derivatives may be separately authorized for SalINTEL indexing and routed as pending SalTHIRA evidence with attribution; no finding or decision is created. Temporary Azure test-job deletion passed. v3.147 is rollback.
- **v3.147 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `cc39bcd58dd043aaf839a5d41c2902e4e9678457`; the immutable image is `sha256:4f03401ed545b7181b4be0c28b3f3557fa2c6ba9222b2ca61d07a694ee2b16d7`. Publication run `35515912887` and governed deployment/live acceptance run `35516139983` passed. Administrator Intake Review, nested-folder reconciliation, bounded decisions and capture, per-item isolation, live Microsoft 365 acceptance, and temporary-job deletion were verified. v3.146 is the rollback release.
- **v3.146 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `063878408a68e8d5c25de26768c157c0eeca99fe`; the immutable image is `sha256:3e13f793e7438dd0b4c5c0a9558aaedca79c15d557b678c17fd76a97e1ee1061`. Governed deployment workflow `35489092343`, live multiformat nested-folder Microsoft 365 acceptance, and temporary Azure test-job deletion passed. v3.145 remains the rollback baseline.
- **v3.142 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `451ebbaa94429ce50db5d721b7cb73c67c8be9c9`; the immutable image is `sha256:092c8506ac490dde32d5885b799fefb446e5fb7ed76dbe003002c5ee5728f290`. Acceptance used the correct `SalCAPA Intake` folder, exercised nested content, preserved governed fail-closed extraction outcomes for human review, and deleted the temporary Azure test job.
- **v3.143 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `51370189b2518bb8fdf6614d34b593eb3d0fc989`; the immutable image is `sha256:ee8ed8282c19473fa2a87d3526b61f7a2c6bd3f186e22f5e3c4f620cc5e8606b`. Live acceptance verified visible sticky assessment navigation, the in-assessment Important Notice, external services navigation, runtime identity and readiness, correct-folder nested Microsoft 365 intake, and temporary-job deletion.
- **v3.144 is frozen, published, deployed, and live accepted.** Frozen source is exact commit `f7ebc34f56237797ff45282112307c384bb880d6`; the immutable image is `sha256:ca0d0f15a559e000de8367b5ab42a57c89d2f6cdedd4164fef79f91baee1cfcc`. It adds audited administrator reconciliation of new, unchanged, changed, and missing sources across the authorized nested Microsoft 365 tree without automatic ingestion or reprocessing. Live multiformat intake acceptance and temporary-job deletion passed.
- The development head now persists administrator-approved, exact-folder Microsoft 365 sources as immutable tenant-scoped materials with source version, timestamp, owner, SHA-256 integrity, classification, audit history, and human-review status. It does not automatically index, create findings, or disclose content.
- **v3.147 is the rollback release** at exact commit `cc39bcd58dd043aaf839a5d41c2902e4e9678457` and immutable image `sha256:4f03401ed545b7181b4be0c28b3f3557fa2c6ba9222b2ca61d07a694ee2b16d7`.nd immutable image `sha256:3e13f793e7438dd0b4c5c0a9558aaedca79c15d557b678c17fd76a97e1ee1061`.

## Source precedence

1. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records.
2. This continuity record after comparison with those GitHub records.
3. Approved architecture and doctrine records referenced by the active milestone.
4. Conversation history only as supporting design context.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

1. Compare this record with the exact development head, open validation pull requests, frozen releases, activation records, and relevant Actions results.
2. Record the exact candidate PR/head, base, gate state, and first/root failing gate.
3. Preserve the distinction among current development, frozen release, published immutable image, deployed runtime, accepted stable release, and rollback baseline.
4. After every required gate is green, close the controlled validation pull request without merge, then advance only the exact verified head through a non-force fast-forward.
5. A failed or inconsistent gate fails closed. Never weaken a security, privacy, accessibility, abuse, recovery, rollback, identity, tenant, disclosure, provenance, or human-authority control to make a release pass.

## Standing controls

- Preserve `main`, `development/v1.17`, `release/v1.16`, every frozen release, and all accepted deployment evidence.
- Human-First Communications and Human Trust & Comprehension doctrine remain in force.
- Preserve canonical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE distinctions.
- Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.
- Keep Microsoft Graph access least-privilege, read-only, exact-folder scoped, auditable, revocable, and separately governed from report publication or other write paths.
