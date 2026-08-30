# Salus THIRA Command v1.0 Release Notes

## Capability Measurement Framework

v1.0 corrects a foundational measurement limitation: capability performance is no longer assumed to be higher-is-better. Each capability now records a measurement type, unit, and comparator and calculates a normalized attainment percentage without hiding the underlying physical measure.

Supported measurement types: Percentage, Time, Count, Rate, Binary, Currency, and Qualitative Rubric. Supported comparators: `>=`, `<=`, and exact `=`.

Examples:
- Emergency notification initiation: target `<= 10 minutes`, actual `8 minutes` → 100% attained.
- Emergency notification initiation: target `<= 10 minutes`, actual `12 minutes` → 83.3% attained, 2-minute physical gap.
- Contact reach: target `>= 95%`, actual `72%` → 75.8% attained.
- Binary control: required `1`, current `1` → 100% attained.

The Command Center, risk analytics, traceability, and executive reporting all use the same governed calculation. Raw target and current values remain visible.

## Governance retained

All v0.9 Accepted Risk, audit/versioning, evidence governance, tenant isolation, OIDC/session controls, portable backup/recovery, SQLite/PostgreSQL runtime, and security controls remain in place.

## Production status

v1.0 is a release-engineered application baseline, not automatic authorization for production use. Environment-specific PostgreSQL/Entra/storage/networking, penetration testing, backup exercises, retention approval, and security/privacy authorization remain required.
