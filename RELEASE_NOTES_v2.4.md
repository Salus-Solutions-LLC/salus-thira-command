# SalCAPA v2.4 release notes

SalCAPA v2.4 adds governed invoice-ready operational statements to SalOPS without representing an accounting invoice or payment transaction.

## Persisted capability

- A statement can be created only after its engagement is closed, its operational estimate is approved, and no reimbursable expense remains unresolved.
- Statement number, immutable line snapshot, totals, variance, provenance, lifecycle, and SHA-256 digest are generated and enforced by the server.
- Billable totals use approved reimbursable expenses only and cannot be supplied or altered by client input.
- Draft, review, approval, and release are distinct persisted transitions; the creator, reviewer, and approver must be independent, and only the recorded approver may release.
- Snapshot integrity is revalidated before every lifecycle transition and retrieval. A mismatch blocks access and records a high-severity security event.
- Protected Members can access only Released member-safe statements. Internal pricing basis, vendors, receipts, evidence links, personnel attribution, draft states, and rejected expenses remain restricted.
- Direct Protected Member access to internal SalOPS entity-version snapshots is denied.
- Tenant-scoped audit/version history, portable backup, relationship validation, and governed restore include invoice-ready statements.

## Release controls

- Deterministic v2.3-to-v2.4 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

Accounting-system integration, tax calculation, invoice issuance, payment collection, and general-ledger posting remain outside this release. No Azure resource, identity, credential, DNS record, or deployment is created by this release.
