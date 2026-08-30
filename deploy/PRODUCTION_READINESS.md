# Salus THIRA Command v1.2 Production Readiness Gate

v1.2 can run natively on either SQLite or PostgreSQL. Production readiness remains fail-closed when SQLite is the active runtime unless an explicit controlled exception is authorized. The preferred production baseline is PostgreSQL plus managed identity/secrets and managed evidence storage.

## Required production baseline

- `SALUS_DB_BACKEND=postgres` and a healthy PostgreSQL runtime reported by `/health/ready`.
- Microsoft Entra/OIDC authentication or another approved OIDC provider.
- Azure Key Vault or another approved managed secret provider.
- Azure Blob Storage or equivalent managed evidence storage.
- ClamAV or an approved malware-scanning service with fail-closed upload policy.
- Redis-backed distributed rate limiting for multiple application replicas.
- Azure Monitor/Application Insights or an approved SIEM destination for centralized security telemetry.
- TLS termination, private networking/firewall restrictions, and approved ingress/WAF controls.
- Portable tenant backups with successful integrity verification and DR validation.
- GitHub CI, dependency audit, Bandit, and CodeQL required before production deployment.
- Documented data-retention/legal-hold rules and an approved records-management schedule.
- Penetration testing and formal security/privacy review before sensitive client data is authorized.

## PostgreSQL cutover controls

- Run `tools/migrate_sqlite_to_postgres.py` only during a controlled write freeze.
- Preserve a pre-cutover portable backup and migration report.
- Require row-count verification and identity-sequence repair.
- Run `tools/postgres_runtime_smoke.py` after migration.
- Compare risk analytics, reports, evidence metadata, and governance counts against the pre-cutover baseline.
- Create and DR-validate a new backup from the PostgreSQL runtime before declaring cutover complete.

See `deploy/POSTGRESQL_CUTOVER.md` for the detailed procedure.
