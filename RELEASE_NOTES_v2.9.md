# SalCAPA v2.9 — governed industry profiles

## Product capability

- Adds tenant-scoped, versioned profiles for government/public safety; critical infrastructure/energy; aviation/transportation/logistics; healthcare/EMS/public health; education/faith/community; and hospitality/events/complex venues.
- Persists reusable terminology, capability guidance, scenario guidance, regulatory-reference metadata, and advisory SalOPS defaults separately from live assessment, evidence, intelligence, personnel, and operational records.
- Requires Draft → In Review → Reviewed → Approved → Published lifecycle gates with independent review and approval, plus governed supersession and retirement.
- Allows authorized tenant configuration to select only a published profile version.
- Snapshots the exact selected profile identity, version, member summary, and service defaults into newly derived assessments and SalOPS services so later profile revisions cannot rewrite historical provenance.

## Trust boundaries

- Clients cannot set tenant ownership, profile keys or versions, publication state, lifecycle actors, audit events, selection provenance, or derived-record snapshots.
- Profile defaults remain advisory and never create verified evidence, qualified intelligence, risk findings, compliance conclusions, expert qualifications, member decisions, operational authorization, or lifecycle state.
- Protected Members receive selected published labels and guidance only. Controlled rationale, internal definitions, reference locators, internal defaults, and authoring history remain restricted to authorized Salus personnel.
- Cross-tenant profile and configuration references fail closed and create high-severity security events.

## Recovery and release controls

- Portable backup and restore include profile definitions, items, immutable events, tenant selections, and derived-record references with relationship and event-sequence validation.
- Deterministic v2.8 → v2.9 reconstruction is retained in `source_archives/v2.9` with target hashes for every generated source file.
- Release gates cover SQLite, PostgreSQL 16, the production container, dependency audit, Bandit, repository hygiene, Azure policy validation, and CodeQL.

## Deployment boundary

No Azure resources, credentials, DNS records, production deployments, external transmissions, proprietary standards imports, accounting integrations, or ChatGPT Sites are created by this release.
