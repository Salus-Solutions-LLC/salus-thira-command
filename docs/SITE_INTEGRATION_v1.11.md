# Salus THIRA Command Site Integration Contract — v1.11

## Purpose

This contract activates persisted threat/hazard and scenario records in the existing private Site. The repository remains authoritative for product semantics, while the Site adapter preserves the same tenant, assessment, relationship, field, audit, and authority boundaries.

## Threat/hazard create contract

The client supplies an assessment ID plus governed threat context: name, category, optional subcategory and description, likelihood, vulnerability, consequence, confidence, trend, inclusion status, and basis. Required text is trimmed and bounded. Scores are integers from 1 through 5. Enumerated governance values fail closed when invalid.

The server verifies that the assessment belongs to the authenticated tenant, generates the identifier, sets status `Active`, and supplies creator, timestamps, and version 1. The client cannot set tenant, status, creator, timestamps, version, audit identity, or lifecycle fields.

## Scenario create contract

The client supplies an assessment ID, a threat ID, a required title and narrative, contextual fields, seven 1–5 impact dimensions, and evidence confidence. The server verifies that the threat exists in the same tenant and assessment. Cross-assessment or cross-tenant relationships fail closed.

Scenario creation cannot supply professional assigned risk, a risk override, authority, approval, lifecycle state, creator, timestamps, or version. Professional risk judgment remains the controlled risk-override action.

## Persistence and operational reads

- Every read and write requires authenticated workspace identity.
- Threat/scenario, audit, and immutable version creation are atomic.
- Lists are assessment-scoped and tenant-isolated.
- Operational counts and relationships are calculated from persisted records only.
- Public responses expose creator name, not creator email.
- Errors do not disclose database, SQL, path, token, or exception detail.
- The Site withholds edit, deletion, risk override, approval, and downstream capability actions until those controlled write paths are connected.

## Release gate

v1.11 may freeze only after deterministic v1.10 reconstruction, SQLite, PostgreSQL 16, Site contract validation, container runtime, dependency audit, Bandit, CodeQL, and release guards are green through a controlled validation pull request that is closed without merge. `main` and prior release branches remain unchanged.
