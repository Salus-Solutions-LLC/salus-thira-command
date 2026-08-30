# Salus THIRA Command Site Integration Contract — v1.10

## Purpose

This contract activates the persisted Assessment Workspace in the existing private Salus THIRA Command Site. The repository remains authoritative for product semantics. The Site adapter may use managed D1 persistence, but it must preserve the same tenant, field, lifecycle, audit, and authority boundaries.

## Assessment record

The create action accepts only:

- `name`: required, trimmed, maximum 160 characters;
- `memberClient`: required, trimmed, maximum 160 characters and mapped to the authoritative `organization` field;
- `assessmentType`: required, maximum 80 characters;
- `purpose`: maximum 2,000 characters;
- `mission`: maximum 2,000 characters;
- `scope`: maximum 4,000 characters;
- `exclusions`: maximum 2,000 characters;
- optional executive sponsor, assessment director, and lead assessor names;
- optional ISO dates for start, target completion, and reassessment; and
- classification: `Standard`, `Restricted`, `Sensitive`, or `Highly Sensitive`.

The server derives the tenant and authenticated creator and sets:

- durable assessment identifier;
- status `Draft`;
- reassessment lifecycle status `Current`;
- empty reassessment overdue and review metadata;
- scope lock false;
- version 1; and
- creation and update timestamps.

Unknown or governance-sensitive fields fail closed. In particular, the client cannot set tenant, status, lifecycle state, overdue state, review identity or time, scope lock, version, creator, or timestamps.

## Authority boundary

Creating an assessment does not approve scope, transition workflow, create a threat or scenario, verify evidence, calculate or assign risk, accept risk, make an executive decision, or resolve a reassessment trigger. Those actions remain separate governed controls.

## Persistence, audit, and reads

- Every read and write requires authenticated workspace identity.
- Tenant scope is derived by the server.
- Assessment and audit creation are atomic.
- Operational counts and lists are computed from persisted records only.
- Responses expose creator name, not creator email.
- Errors are controlled and do not disclose SQL, database, path, token, or exception detail.
- The Site withholds edit, workflow, approval, and lifecycle actions until those governed write paths are connected.

## Release gate

v1.10 may freeze only after deterministic v1.9 reconstruction, SQLite, PostgreSQL 16, Site contract validation, container runtime, dependency audit, Bandit, CodeQL, and release guards are green through a controlled validation pull request that is closed without merge. `main` and prior release branches remain unchanged.
