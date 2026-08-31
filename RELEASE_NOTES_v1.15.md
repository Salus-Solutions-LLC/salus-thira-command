# Salus THIRA Command v1.15 — Operational Risk and Professional Judgment Workspace

v1.15 makes the existing risk model and professional-judgment controls operational as one governed workspace without conflating calculated and professionally assigned risk.

## Product capability

- Inherent, calculated current, predicted residual, validated residual, and professional assigned risk remain distinct fields and histories.
- Calculated risk is server-derived from assessment-scoped threat, scenario, capability, improvement, decision, and evidence state.
- A professional judgment requires a named authority, documented reason, bounded assigned score, and future review date.
- Optional supporting evidence must belong to the same assessment and be Verified and lifecycle Current.
- Stale, expired, missing, or no-longer-Verified supporting evidence stops a judgment from supplying current assigned risk without changing calculated risk.
- Overdue review state also stops assigned-risk applicability until a controlled review is completed.
- Controlled renewal verifies cited evidence remains eligible before restoring review currency.
- A new judgment supersedes the prior active judgment; withdrawal and supersession preserve the complete record.
- Creation, automatic overdue state, controlled review, supersession, and withdrawal write audit and immutable version history.
- Generic payloads cannot forge calculated values, bands, lifecycle state, audit, tenant, or timestamp fields.
- Risk analytics, traceability, executive outputs, and backups retain calculated basis and professional-judgment history.

## Release safety

The frozen v1.14 source is reconstructed and hash-verified before the deterministic v1.15 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release-entrypoint, and repository-boundary gates remain mandatory. The validation pull request closes without merge, and `main` plus every prior frozen release remain unchanged.
