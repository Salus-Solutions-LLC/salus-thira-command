# SalCAPA v2.6 release notes

SalCAPA v2.6 delivers a governed See–Coordinate–Act Common Operating Picture for Protected Members and authorized Salus personnel.

## Persisted capability

- See presents tenant-scoped, member-safe intelligence, risks, alerts, operational progress, released deliverables, and submitted observations without exposing source narratives, locators, internal planning, draft work, personnel, or restricted evidence.
- Coordinate provides persisted discussion threads with server-controlled ownership, lifecycle, timestamps, participant roles, and Shared or Salus Internal message boundaries.
- Act provides governed member decision requests tied to authorized SalINTEL, SalTHIRA, SalOPS, engagement, observation, or report sources.
- Salus personnel issue requests from server-defined decision types and allowed choices; clients cannot forge tenant, authority, status, provenance, choices, or lifecycle state.
- Only the designated Protected Member Client Executive may record a decision. Contributor and Auditor roles cannot exercise executive authority.
- Recorded decisions are immutable. Pending requests may be withdrawn by authorized Salus personnel, and later recurring requests remain independently traceable.
- Coordination and decision histories use ordered immutable event records, tenant-isolated audit entries, and portable backup and governed restore.
- Existing executive decisions and accepted-risk records now stamp authenticated server-side authority even when older clients submit a legacy authority field.

## Release controls

- Deterministic v2.5-to-v2.6 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

This release does not dispatch emergency services, transmit information externally, activate Azure resources, change DNS, deploy production, or create a ChatGPT Site.
