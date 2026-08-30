# Salus THIRA Command v1.10 — Operational Assessment Workspace

v1.10 activates governed assessment creation and retrieval as the foundation for the operational product workspace.

## Product capability

- Authenticated users can create tenant-isolated assessment workspaces for a Member Client.
- The accepted input contract is limited to assessment name, Member Client, assessment type, purpose, mission, scope, exclusions, leadership, dates, and classification.
- Status is server-set to `Draft`; reassessment lifecycle is server-set to `Current`; tenant, creator, timestamps, review state, scope lock, and version cannot be supplied by the client.
- Required text is trimmed and bounded, dates are normalized, and unknown or governance-sensitive fields fail closed.
- Every assessment creation writes audit and immutable version history in the same transaction.
- Existing controlled workflow transitions, scope lock/change history, and reassessment review remain the only ways to alter governed state.
- Tenant backups include assessments, audit history, and entity versions.
- The private product Site implements the same authority boundary with managed persistence and atomic assessment-plus-audit creation.

## Release safety

The frozen v1.9 source is reconstructed and hash-verified before the deterministic v1.10 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain mandatory. `main` and all prior frozen release branches remain unchanged.
