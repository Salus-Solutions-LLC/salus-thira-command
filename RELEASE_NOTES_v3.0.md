# SalCAPA v3.0 — operating-model acceptance and authority hardening

## Verified operating model

- Exercises one persisted journey from Protected Member observation through governed SalINTEL qualification, SalTHIRA assessment and prioritization, Protected Member decision, SalOPS engagement, qualified expert execution, released reporting, financial statement, and reassessment feedback.
- Verifies the See–Coordinate–Act Common Operating Picture and member-facing APIs exclude controlled source, personnel, location, communications, tactics, vendor, receipt, pricing-basis, and draft details.
- Verifies immutable report and invoice-ready snapshots, linked audit/version history, tenant-scoped portable recovery, and independent restore authorization.

## Hardened authority boundaries

- Restricts executive decisions, accepted-risk decisions, scope decisions, Common Operating Picture decisions, and SalOPS request authorization to an authenticated Protected Member Authority (`Client Executive`).
- Records denied attempts by Salus administrative or operational roles as high-severity `MEMBER_AUTHORITY_DENIED` security events.
- Allows an accepted, qualified expert to advance only tasks assigned to that expert while retaining SalOPS coordinator authority over other task assignments.
- Records cross-tenant operational task actions as high-severity security events and fails closed.

## Release controls

- Adds a complete operating-model acceptance harness to SQLite, PostgreSQL 16, and production-container gates.
- Retains deterministic v2.9 → v3.0 reconstruction and fresh dependency-audit, Bandit, repository-hygiene, Azure-policy, and CodeQL gates.

## Deployment boundary

No Azure resources, credentials, DNS records, production deployments, external transmissions, accounting invoices, payment processing, proprietary standards imports, or ChatGPT Sites are created by this release.
