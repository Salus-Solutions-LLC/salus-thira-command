---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 21 September 2026 18:30 CDT
current_frozen_release: v3.153
current_frozen_commit: a0fc3244203e51ad524683fb7e63868de876f4ce
active_development_branch: development/salcapa-platform
current_development_head: ecfa9b10c514b42eab8850dd3041a008e2658cce
active_product_milestone: issue_370_governed_document_ingestion
active_build_system_issue: 370
active_increment: protection_advisor_report_contract_compatibility
last_completed_increment: protection_advisor_v3153_report_generation_acceptance
candidate_release: v3.154
validation_pr: pending
validation_branch: release/v3.154
validation_base: development/salcapa-platform
validation_head: ecfa9b10c514b42eab8850dd3041a008e2658cce
validation_gate_state: preflight
failed_workflows: none
first_root_failing_gate: none
root_cause: none
repair_head: ecfa9b10c514b42eab8850dd3041a008e2658cce
repair_summary: protection_advisor_report_contract_compatibility_repair
genuine_blockers: none
next_authorized_step: complete_v3154_validation_then_publish_and_deploy
deployed_demo_release: v3.150
deployed_demo_state: protection_advisor_anonymous_review_button_repaired_live_verified_and_nested_m365_acceptance_passed_with_temporary_job_deleted
---




# SalCAPA build continuity




This non-sensitive engineering record is the restart point for the unified SalCAPA build. GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records. Those records control whenever they disagree with this file.




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
