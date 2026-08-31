# Salus THIRA Command v1.12 — Operational Capability Target Workspace

v1.12 activates governed capability-target creation and direction-aware performance measurement inside persisted Member Client assessment workspaces.

## Product capability

- Authenticated users can create tenant-isolated capability targets within an assessment.
- A capability may be linked to a scenario only when that scenario belongs to the same tenant and assessment.
- Required standard and current performance remain separate authoritative values.
- Percentage, time, count, rate, binary, currency, and qualitative-rubric measurements are supported.
- Greater-than-or-equal, less-than-or-equal, and equality targets are evaluated direction-aware; binary targets require equality and values of zero or one.
- Attainment, performance gap, and target status are calculated by the server and cannot be supplied by the client.
- Mission area, capability family, outcome, operating conditions, metric, responsibility, dependencies, evidence requirement, confidence, and validation dates are retained with the record.
- Tenant, creator, timestamps, version, and calculated outputs are server controlled.
- Cross-assessment and cross-tenant relationships fail closed.
- Every creation writes audit and immutable version history atomically.
- The private Site adapter implements the same authority boundary using managed persistence and displays calculations from persisted records only.

## Release safety

The frozen v1.11 source is reconstructed and hash-verified before the deterministic v1.12 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain mandatory. `main` and prior frozen release branches remain unchanged.
