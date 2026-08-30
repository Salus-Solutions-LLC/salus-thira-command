# Salus THIRA Command v1.4 Release Notes

v1.4 adds governed evidence lifecycle management without changing the risk-scoring methodology.

## Evidence lifecycle

- Adds `valid_until`, `lifecycle_status`, stale reason/time, and lifecycle-review metadata to evidence records.
- Keeps verification and lifecycle separate: evidence may remain **Verified** while becoming **Stale**.
- Automatically marks Verified evidence Stale after its validity date passes.
- Creates one unresolved `Evidence Lifecycle / Evidence Stale` reassessment trigger per stale episode.
- Escalates the stale trigger to High when the evidence supports a validated improvement or active professional risk override.
- Requires a controlled lifecycle review with a new current/future validity date and documented outcome to restore Current status.
- Prevents generic edits from forging lifecycle state or renewing already-stale evidence outside the controlled review action.

## Risk and decision integrity

- Stale evidence immediately stops earning validated-residual-risk credit.
- Stale evidence cannot support a new improvement validation or professional risk override.
- Existing professional risk judgments remain preserved rather than being silently deleted; reports explicitly show whether cited evidence is current.
- Application version advances to **1.4.0** while risk methodology remains **1.1.0**.

## Authoritative outputs

Evidence lifecycle is refreshed before dashboard metrics, evidence lists, risk analytics, executive packages/reports, assessment exports, and tenant backup capture. Repeated authoritative reads do not create duplicate unresolved stale triggers.

## Release acceptance

The release gate requires deterministic v1.3→v1.4 source reconstruction, Python/JavaScript validation, SQLite and PostgreSQL 16 lifecycle smokes, PostgreSQL transaction smoke, dependency audit, Bandit, and fail-closed local CodeQL analysis.
