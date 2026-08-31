# Salus THIRA Command v1.13 — Operational Evidence Lifecycle Workspace

v1.13 hardens governed evidence creation and activates the complete evidence-currency lifecycle for operational assessment workspaces.

## Product capability

- Evidence records are tenant-isolated and may reference only capabilities and scenarios in the same assessment.
- Verification status remains separate from lifecycle currency: evidence may be Verified and Stale.
- Evidence input uses a strict field allowlist, bounded text, governed enumerations, finite relationship identifiers, and normalized ISO dates.
- Tenant, lifecycle status, stale reason, stale timestamp, lifecycle reviewer, review timestamp, audit identity, timestamps, and versions are server controlled.
- Expired evidence automatically becomes Stale and creates one open reassessment trigger without duplication.
- Controlled lifecycle review requires a documented review note and a current or future validity date before restoring evidence to Current.
- Review resolves the associated stale-evidence trigger and records audit and immutable version history atomically.
- Stale evidence automatically loses validated-risk credit and cannot satisfy professional-risk-override evidence requirements.
- Automated lifecycle sweeps remain outside active write transactions so SQLite and PostgreSQL behavior remains identical.

## Release safety

The frozen v1.12 source is reconstructed and hash-verified before the deterministic v1.13 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain mandatory. `main` and prior frozen release branches remain unchanged.
