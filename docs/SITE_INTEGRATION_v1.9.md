# Salus THIRA Command Site Integration Contract — v1.9

## Purpose

This contract defines the first operational write path from the private Salus THIRA Command Site into governed product data. The repository remains authoritative for product semantics. A presentation adapter may use platform persistence, but it must implement these rules exactly and must not invent approval, evidence, risk, decision, or lifecycle state.

## Governed intake record

A governed intake record is an append-only pre-disposition record with:

- `id`: server-generated durable identifier using the `INT-` namespace;
- `tenant_key`: server-derived tenant boundary, never client supplied;
- `record_type`: exactly `Observation`, `Evidence Lead`, `Discovery`, or `Decision Input`;
- `title`: required, trimmed, maximum 160 characters;
- `details`: required, trimmed, maximum 4,000 characters;
- `source_context`: required, trimmed, maximum 500 characters;
- `status`: server-set to `Draft`;
- authenticated creator identity and server timestamp; and
- `version`: server-set to 1.

The create action accepts only record type, title, details, and source context. Unknown or governance-sensitive fields fail closed. In particular, the client cannot set tenant, status, verification, lifecycle, risk, approval, disposition, reviewer, decision, version, creator, or timestamps.

## Authority boundary

Creating governed intake:

- does not create or modify an assessment;
- does not promote a discovery candidate;
- does not verify evidence or make it Current;
- earns no calculated, predicted, or validated-risk credit;
- does not create a professional risk override;
- does not accept risk;
- does not create, approve, or renew an executive decision; and
- does not resolve a reassessment trigger.

A later controlled disposition must promote or reject the draft through an explicit governed action. Generic update is intentionally absent.

## Authentication, tenancy, and audit

- Every read and write requires authenticated workspace identity.
- Tenant scope is derived by the server.
- Creation persists the intake record and an audit event atomically.
- Public responses do not expose creator email.
- Operational metrics are computed from persisted records; the interface must not display synthetic counts as live data.
- External error responses are controlled and contain no database, SQL, path, token, or exception detail.

## Adapter behavior

The private Site adapter uses its managed D1 binding for the operational presentation store. It uses prepared statements and a single transactional batch for record plus audit creation. Generated, versioned migrations own schema changes; runtime code does not create or alter tables.

The authoritative FastAPI/PostgreSQL implementation added during v1.9 must preserve the same field allowlist, state boundary, tenant derivation, audit semantics, and response shape. SQLite, PostgreSQL 16, and Site-adapter conformance tests must use the same contract fixtures.

## Release gate

v1.9 may freeze only after deterministic v1.8 reconstruction, SQLite, PostgreSQL 16, Site contract checks, container runtime, dependency audit, Bandit, CodeQL, and release guards are green through a controlled validation pull request that is closed without merge. main and prior release branches remain unchanged.
