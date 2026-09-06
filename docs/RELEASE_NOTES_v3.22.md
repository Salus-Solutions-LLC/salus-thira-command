# SalCAPA v3.22 release notes

## Protective Readiness operating environment

- Adds a server-derived Protective Readiness lifecycle summary to the Common Operating Picture.
- Calculates See, Decide, Act, and Prove indicators only from tenant-scoped persisted records.
- Keeps lifecycle counts, authority, completion, evidence, verification, and reassessment state server-controlled.
- Repositions the member experience around “See risk early. Decide with confidence. Act in time. Prove the work was done.”
- Renames the executive output to the SalCAPA Protective Readiness Executive Briefing.
- Adds explicit SalTHIRA attribution discipline: Salus applies a specific methodology informed by recognized THIRA principles and does not claim ownership of the public framework.
- Extends SQLite, PostgreSQL 16, and production-container acceptance coverage for the persisted lifecycle and member-facing language.

## Governance

This candidate preserves all frozen releases, `main`, and `development/v1.17`. It does not change DNS, deploy a Container App, introduce a client secret, or broaden Azure scope.
