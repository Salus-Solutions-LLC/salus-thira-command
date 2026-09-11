# SalCAPA report release boundary

## Purpose

Salus personnel prepare, review, approve, and release governed reports. Protected Members receive only the report version that an authorized person released. A Draft, Reviewed, or Approved report remains Salus work product and is not discoverable or deliverable to a Protected Member.

## Delivery contract

- Report lists shown to Protected Members contain Released versions only.
- Direct snapshot access returns no report until the version is Released.
- Protected Member JSON, CSV, and printable HTML delivery use the latest Released immutable snapshot for the requested assessment.
- Every delivered format carries the Released state and the snapshot hash as its ETag.
- A later change to working assessment records does not silently change an already released report.
- Internal Salus roles retain live previews for preparation and review, subject to their existing role, tenant, assessment, and sensitivity controls.
- A tenant cannot discover or retrieve another tenant's report.
- Snapshot-integrity failure stops delivery and records a security event.

## Human authority

Technology supports preparation and delivery; it does not create release authority. The existing Draft → Reviewed → Approved → Released lifecycle remains controlling. No report is treated as released merely because a draft was prepared, a file format was requested, or a Protected Member has access to the assessment.

## Validation

The accepted-v3.36 migration and recovery rehearsal verifies the boundary on SQLite, PostgreSQL 16, and the production container. It tests internal Draft access, Protected Member nondisclosure before release, distinct review/approval/release authorities, immutable delivery after release, cross-tenant denial, member-safe assessment fields, CSV/HTML/JSON consistency, and preservation through recovery and rollback.
