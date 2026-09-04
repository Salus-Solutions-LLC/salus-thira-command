# SalCAPA v2.5 release notes

SalCAPA v2.5 adds governed observation and concern intake without treating a report as verified intelligence, evidence, a threat finding, or an operational order.

## Persisted capability

- Authenticated Protected Members can submit structured observations with an explicit emergency-channel warning, reporter-contact choice, location, time, context, reported urgency, report-on-behalf-of handling, and optional attachment.
- Administrators can create expiring public intake channels. Channel tokens and one-time submission receipts are server-generated, stored only as hashes, and never returned by listing APIs.
- Anonymous and confidential-contact reports receive server-enforced Salus Restricted source protection; public submissions are excluded from Protected Member listings.
- Observation attachments are size-limited, malware-scanned, hashed, stored under tenant/observation paths, integrity-checked on retrieval, and governed by inherited retention and legal-hold controls.
- Submitted, Acknowledged, Triaged, Routed, and Closed states are controlled server-side with immutable event snapshots and tenant-scoped audit records.
- Authorized routing may create one new SalINTEL collection record, SalTHIRA reassessment trigger, or SalOPS request. External escalation records a reference only; SalCAPA does not transmit information.
- Protected Members receive limited acknowledgement and disposition fields. Reporter identity, contact, narrative, source restrictions, triage notes, assignments, and attachment access remain need-to-know.
- Portable backup and governed restore preserve channels, observations, attachments, event history, downstream relationships, retention, and legal hold.

## Release controls

- Deterministic v2.4-to-v2.5 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

This release does not provide emergency dispatch, promise absolute confidentiality, verify allegations automatically, send external notifications, activate Azure resources, change DNS, or deploy production.
