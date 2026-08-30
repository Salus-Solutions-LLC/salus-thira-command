# Salus THIRA Command v1.4 Release Notes

## Evidence lifecycle governance

v1.4 adds time-aware evidence validity without changing the v1.1 risk-scoring methodology.

### Added

- `valid_until` and separate `lifecycle_status` fields for evidence.
- Automatic Current → Stale transition after validity expiry.
- One accountable Evidence Lifecycle reassessment trigger per stale episode.
- High trigger severity when stale evidence supports a validated improvement or active professional risk override; Moderate otherwise.
- Controlled lifecycle review to restore Current status with a new validity date and documented review basis.
- Audit and revision snapshots for automatic stale transitions and lifecycle reviews.
- Command Center stale-evidence metric.
- Evidence lifecycle status in executive CSV/HTML reports and assessment exports.
- Visible warning when an active professional risk override is supported by evidence that has become stale.

### Fail-closed behavior

- Stale or expired evidence cannot support a new improvement validation.
- Stale or expired evidence cannot support a new professional risk override.
- Validated residual-risk credit is removed automatically when its validation evidence becomes stale and returns only when evidence is again Current and Verified.
- Generic record edits cannot forge lifecycle status, stale timestamps, or validity changes; restoration requires the controlled lifecycle-review action.

### Preserved behavior

- Professional assigned risk remains separate from calculated risk.
- Existing professional judgment records are not silently withdrawn when supporting evidence becomes stale; the support condition is surfaced and reassessment is triggered.
- Verification and lifecycle status remain separate concepts.
- Application version advances to 1.4.0 while risk methodology remains 1.1.0.

### Release acceptance

The release gate requires exact source reconstruction, Python/JavaScript validation, SQLite and real PostgreSQL 16 lifecycle smoke tests, PostgreSQL transaction smoke, dependency audit, Bandit, and fail-closed local CodeQL analysis.
