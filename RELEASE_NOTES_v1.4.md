# Salus THIRA Command v1.4 Release Notes

## Evidence lifecycle governance

v1.4 separates evidence verification from evidence validity. A record may remain **Verified** while becoming **Stale** after its governed validity date passes.

### New controls

- Evidence records add `valid_until`, `lifecycle_status`, stale reason/timestamp, and lifecycle-review actor/timestamp.
- Expired Verified evidence is automatically marked Stale before authoritative risk, evidence, dashboard, report/export, and backup operations.
- One unresolved **Evidence Lifecycle / Evidence Stale** reassessment trigger is maintained per stale record.
- Trigger severity becomes High when the evidence supports a validated improvement or active professional risk override.
- Stale evidence cannot support a new improvement validation or professional risk override.
- Stale evidence automatically stops earning validated-residual-risk credit.
- A controlled lifecycle-review action is required to return evidence to Current status; ordinary record edits cannot forge lifecycle fields.
- Lifecycle review requires Verified evidence, a current/future validity date, and a documented outcome, and it resolves the stale-evidence trigger while preserving audit/version history.

## Methodology invariants

- Application version: **1.4.0**
- Risk methodology version: **1.1.0**
- Calculated, professional assigned, predicted residual, and validated residual risk remain separate governed concepts.
- v1.3 professional-risk overrides, v1.2 relational integrity, v1.1 governed residual-risk validation, and v1.0 direction-aware capability measurement remain in force.

## Release acceptance

The release gate requires deterministic source reconstruction, Python and JavaScript validation, shared SQLite/PostgreSQL 16 evidence-lifecycle smoke, PostgreSQL transaction testing, dependency audit, Bandit, and fail-closed local CodeQL Python analysis with SARIF preservation.
