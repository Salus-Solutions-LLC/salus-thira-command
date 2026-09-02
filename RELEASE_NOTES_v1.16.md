# Salus THIRA Command v1.16 — Executive Decisions and Accepted Risk Workspace

v1.16 makes executive disposition and accepted-risk governance operational as one persisted workspace.

## Product capability

- Executive decisions are assessment-scoped, tenant-isolated, append-only records with enumerated decision types.
- Named authority, documented rationale, finite nonnegative funding, and validated dates are enforced server-side.
- Accept Risk requires explicit residual exposure, accountable ownership, a reconsideration trigger, and a future review date.
- An Accept Risk decision and its accepted-risk register record commit atomically.
- Client payloads cannot forge provenance, authority, lifecycle state, timestamps, audit history, or versions.
- Accepted-risk status changes use controlled transitions with a documented basis; Closed and Superseded records cannot be reopened.
- Overdue decision and accepted-risk reviews generate one reassessment trigger per lifecycle episode.
- Controlled reviews restore Current lifecycle state and resolve only their corresponding lifecycle triggers.
- Terminal accepted-risk transitions resolve open lifecycle triggers while preserving history.
- Executive reports, traceability, and portable backups retain decision and accepted-risk records.

## Release safety

The frozen v1.15 source is reconstructed and hash-verified before the deterministic v1.16 delta is applied. SQLite, PostgreSQL 16, production container, dependency audit, Bandit, CodeQL, release-entrypoint, and repository-boundary gates remain mandatory. The validation pull request closes without merge, and `main` plus every prior frozen release remain unchanged.
