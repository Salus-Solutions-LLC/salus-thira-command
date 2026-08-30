# Salus THIRA Command v1.11 — Operational Threat and Scenario Workspace

v1.11 activates governed threat/hazard and scenario creation inside persisted Member Client assessment workspaces.

## Product capability

- Authenticated users can create tenant-isolated threat/hazard records within an assessment.
- Threat inputs explicitly capture category, description, likelihood, vulnerability, consequence, confidence, trend, inclusion disposition, and supporting basis.
- Likelihood, vulnerability, and consequence are constrained to the governed 1–5 scales.
- Threat status is server-set to `Active`; tenant, status, creator, timestamps, and version cannot be supplied by the client.
- Authenticated users can create contextual scenarios linked to a threat in the same assessment.
- Scenario records capture narrative, initiating event, location, duration, operating conditions, dependencies, decision points, assumptions, uncertainties, impact dimensions, and evidence confidence.
- Cross-assessment and cross-tenant threat/scenario relationships fail closed.
- Every creation writes audit and immutable version history.
- Scenario creation cannot forge a professional risk override; professional judgment remains a separate controlled action.
- The private Site adapter implements the same authority boundary using managed persistence and atomic record, audit, and version creation.

## Release safety

The frozen v1.10 source is reconstructed and hash-verified before the deterministic v1.11 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain mandatory. `main` and prior frozen release branches remain unchanged.
