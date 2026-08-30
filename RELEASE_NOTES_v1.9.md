# Salus THIRA Command v1.9 — Governed Product Intake and Site Integration

v1.9 establishes the first operational write path from the approved private Command Center into governed, durable product records.

## Product capability

- Authenticated users can capture Observations, Evidence Leads, Discoveries, and Decision Inputs.
- Records are tenant-isolated, append-only at intake, server-identified, timestamped, and audited.
- The create contract accepts only record type, title, details, and source context.
- Status, tenant, creator, timestamps, version, verification, lifecycle, risk, approval, disposition, and decision fields cannot be supplied by the client.
- Every new record is a Draft. It earns no evidence or risk credit and grants no approval or decision authority.
- Operational counts and newest-record lists are computed from persisted data.
- Tenant backups include governed intake records and restore them in controlled order.
- The private Site adapter implements the same contract with managed persistence and atomic record-plus-audit creation.

## Release safety

The v1.8 source is reconstructed and hash-verified before the deterministic v1.9 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain required. main and all prior release branches remain unchanged.
