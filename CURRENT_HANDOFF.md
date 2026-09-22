# Salus Solutions — Current Handoff

**Handoff date:** 22 September 2026  
**Current production release:** SalCAPA 3.163  
**Rollback release:** SalCAPA 3.162  
**Authoritative repository:** `Salus-Solutions-LLC/salus-thira-command`  
**Working branch:** `development/salcapa-platform`

## Current objective

Build the governed knowledge-promotion workflow from **OneDrive → SalCAPA Intake → 10 Pending Classification** to **SharePoint → Salus Knowledge Sources**, while preserving human approval, provenance, duplicate controls, access boundaries, and recoverability.

## Completed and deployed

- SalCAPA 3.163 is deployed and the authenticated Protection Advisor professional PDF download was manually confirmed by Marc.
- SalCAPA 3.162 remains the rollback baseline.
- The eleven enterprise-knowledge folders exist in **Salus Knowledge Sources**.
- The four intake workflow folders exist under **OneDrive → SalCAPA Intake**.
- Restricted **Protected Member Records** and **System Governance** libraries exist in the SalCAPA SharePoint site.
- The Protected Member relationship foundation, engagement dashboard, and Start New Assessment workflow are present on the development branch but are not yet released.

## Approved knowledge workflow

1. SalCAPA detects only files beneath `10 Pending Classification`.
2. It captures exact bytes, Microsoft item identity, version/eTag, path, timestamps, owner, size, MIME type, and SHA-256.
3. It identifies likely duplicates and creates an immutable review candidate without approving or indexing it.
4. An authorized human classifies the candidate as Approved, Deferred, Duplicate, Unsupported, Sensitive, or Excluded.
5. Approved content requires a mapped enterprise-knowledge folder and explicit permitted-product scope.
6. SalCAPA copies approved bytes to the mapped **Salus Knowledge Sources** folder and verifies the destination hash.
7. The source remains in intake by default. Removal is permitted only after verified promotion, retention reconciliation, and a separate enabled authorization.
8. Any source version change after approval invalidates approval and requires re-review.

## Current implementation status

- Continuity records were recovered from the project Library after they were found absent from the Git branch.
- The recovered 3.161 handoff was reconciled to the verified 3.163 production state.
- A local implementation provides candidate capture, classification, promotion, destination verification, source-change invalidation, event history, and default source retention.
- Development commit `3470ad100ab495eba23e7f0fe7ed64058bd7780f` contains the restored continuity records, approved architecture, workflow implementation, application registration, environment contract, and CI gate.
- CI, the production-container build, PostgreSQL validation, CodeQL, contextual intake, and Protection Advisor regression all passed on that exact commit.
- No Microsoft 365 business content has been moved, copied, or deleted by this implementation.
- No release or production deployment has been made for this workflow.

## Exact next action

Resolve and verify the production **Salus Knowledge Sources** drive and root-folder identifiers and the application's least-privilege destination permission. Then add reviewer workflow acceptance, run a non-sensitive representative-file pilot with source removal disabled, and only afterward prepare a governed release candidate.

## Acceptance criteria

- Only candidates beneath `10 Pending Classification` are captured.
- Capture is idempotent by source drive, item, and eTag.
- Hash-matched promoted content is flagged for duplicate review.
- Promotion cannot occur without human approval.
- Approved destinations are limited to the registered enterprise-knowledge taxonomy.
- Destination bytes are independently verified against the captured SHA-256.
- A changed source cannot use a stale approval.
- Source removal is disabled by default and never precedes verified destination delivery.
- Every capture, decision, promotion, verification, and removal outcome is auditable.
- No item is automatically indexed into SalINTEL or exposed to ChatGPT merely because it was uploaded or promoted.

## Unfinished or uncertain

- Production destination drive and root-folder identifiers must be added through governed Azure configuration.
- Application write permission to the explicit knowledge destination must be verified as least privilege.
- Reviewer UI and live representative-format acceptance remain to be completed.
- The first pilot should use no more than 25 non-sensitive representative documents.
- Source removal must remain disabled until retention and recovery acceptance are separately approved.
