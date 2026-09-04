# SalCAPA v2.3 release notes

SalCAPA v2.3 adds governed operational estimating and actual-expense control to SalOPS.

## Persisted capability

- Operational estimates are created from server-calculated line items and retain immutable tenant, engagement, assessment, provenance, lifecycle, and approval fields.
- Estimate submission and decision are separate actions. The submitting actor cannot approve or reject the same estimate.
- Actual expenses are tied to a governed engagement and may reference only a task in that engagement and evidence in its assessment.
- Expense totals are calculated server-side; submission and approval are separate, accountable actions.
- Approved estimate, approved reimbursable actual, and remaining-estimate values are calculated consistently in USD.
- Authorized Salus personnel can see controlled estimating basis, line detail, vendors, evidence links, and lifecycle attribution.
- Protected Members see member-safe submitted/approved estimates and aggregate approved actuals only. Internal basis, vendors, receipts, personnel, and draft or rejected expenses are not disclosed.
- Estimate and expense transitions are preserved in tenant-scoped audit and entity-version history.
- Portable backup and governed restore preserve and validate estimates, lines, expenses, task relationships, evidence relationships, and tenant boundaries.

## Release controls

- Deterministic v2.2-to-v2.3 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

Invoice issuance, accounting-system integration, and payment processing are intentionally excluded from v2.3. No Azure resource, identity, credential, DNS record, or deployment is created by this release.
