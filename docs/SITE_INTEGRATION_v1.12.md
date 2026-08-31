# Salus THIRA Command Site Integration Contract — v1.12

## Purpose

This contract activates persisted capability targets in the existing private Site. The repository remains authoritative for product semantics, while the Site adapter preserves the same tenant, assessment, scenario, field, calculation, audit, and authority boundaries.

## Capability-target create contract

The client supplies an assessment ID, an optional scenario ID, a required name, governed context, a measurement type and comparator, required standard, current performance, confidence, and optional validation dates. Required text is trimmed and bounded. Numeric values must be finite. Enumerated values and ISO dates fail closed when invalid.

The server verifies that the assessment belongs to the authenticated tenant. When supplied, the scenario must belong to that tenant and assessment. The server generates the identifier and supplies creator, timestamps, and version 1. The client cannot set tenant, creator, timestamps, version, audit identity, attainment, gap, or target status.

## Direction-aware performance contract

- `>=` measures progress toward a minimum required standard.
- `<=` measures progress toward a maximum acceptable value, including time-to-perform targets.
- `=` measures distance from the exact required standard.
- Binary measurements use `=` with values limited to zero or one.
- Attainment is bounded from 0 through 100 percent.
- Status is `Met` at 100 percent, `Near Target` at 80 through less than 100 percent, and `Below Target` below 80 percent.

## Persistence and operational reads

- Every read and write requires authenticated workspace identity.
- Capability, audit, and immutable version creation are atomic.
- Lists are assessment-scoped and tenant-isolated.
- Operational counts and calculations are derived from persisted records only.
- Public responses expose creator name, not creator email.
- Errors do not disclose database, SQL, path, token, or exception detail.
- The Site withholds edit, deletion, evidence linking, gap creation, and approval actions until those controlled write paths are connected.

## Release gate

v1.12 may freeze only after deterministic v1.11 reconstruction, SQLite, PostgreSQL 16, Site contract validation, container runtime, dependency audit, Bandit, CodeQL, and release guards are green through a controlled validation pull request that is closed without merge. `main` and prior release branches remain unchanged.
