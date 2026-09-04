# SalCAPA v2.8 release notes

SalCAPA v2.8 delivers governed expert qualification, availability, conflict review, and engagement assignment for SalOPS.

## Persisted capability

- Tenant-scoped expert profiles separate approved member identity, biography, role, and contact summaries from controlled personnel history, disciplines, jurisdictions, and regions.
- Draft profiles require activation by operational authority independent from both the expert and the material editor. Active assignments block profile deactivation.
- Credentials are recorded as unverified and require an independent verifier. Verified credential evidence must remain current; active assignments block withdrawal.
- Availability is persisted independently and must cover the engagement operating period.
- Each assignment requires a current verified credential and a conflict disclosure independently cleared by a reviewer distinct from both the expert and assignment authority.
- Assignment status is server-controlled. The assigned expert alone may accept; independent operational authority controls release.
- Member identity, qualification, and service context are snapshotted at proposal so later source changes cannot rewrite historical provenance.
- Catalog-backed expert-enabled engagements cannot mobilize without an accepted qualified assignment. Assignment-linked tasking resolves the assignee from the server-held profile.
- Protected Members see only accepted, explicitly visible expert identity, role, biography, contact, and status snapshots. Internal biography, credentials, availability, conflict detail, qualification basis, and staffing provenance remain restricted.
- Profiles, credentials, availability, conflicts, assignments, immutable event histories, audit records, and assignment-linked tasks are included in portable backup and governed restore.

## Release controls

- Deterministic v2.7-to-v2.8 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

This release does not activate Azure resources, create credentials, change DNS, deploy production, transmit information externally, or create a ChatGPT Site.
