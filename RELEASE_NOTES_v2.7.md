# SalCAPA v2.7 release notes

SalCAPA v2.7 delivers the governed SalOPS service catalog and catalog-backed engagement readiness lifecycle.

## Persisted capability

- Four canonical SalOPS pillars organize Readiness and Preparedness, Protective Operations, Incident and Crisis Support, and Recovery and Sustainment services.
- Versioned service definitions separate member descriptions and deliverables from controlled internal scope, readiness inputs, and authorization requirements.
- Draft, independent review, independent approval, publication, supersession, and retirement are server-controlled and preserved as immutable catalog events.
- Protected Members see and request only active published member-safe services. The server snapshots the authoritative service key, version, description, and deliverables into each request.
- Authorized requests become Salus-controlled engagements whose service provenance remains pinned even after the catalog is revised.
- Catalog-backed engagements require persisted readiness records before mobilization and resolution of every readiness item before activation.
- Protected Members receive only approved service definitions, member-safe readiness items and counts, operational status, and released deliverables. Internal tactics, staffing, vendors, credentials, locations, communications, and draft plans remain restricted.
- Catalog, request snapshots, engagement provenance, readiness state, audit records, and immutable events are tenant-isolated and included in portable backup and governed restore.

## Release controls

- Deterministic v2.6-to-v2.7 source reconstruction and verification.
- Fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy, and CodeQL gates.
- Controlled validation pull request must be closed without merge.

This release does not activate Azure resources, create credentials, change DNS, deploy production, transmit information externally, or create a ChatGPT Site.
