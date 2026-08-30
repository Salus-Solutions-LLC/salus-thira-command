# PostgreSQL Cutover Runbook — Salus THIRA Command v1.4

v1.4 supports SQLite and PostgreSQL runtime providers. Production cutover is a controlled change.

## Preconditions

1. Freeze writes to the source SQLite environment.
2. Create and DR-validate a v1.4 portable tenant backup.
3. Verify SQLite with `PRAGMA integrity_check`.
4. Provision PostgreSQL with TLS and an approved identity model.
5. Configure networking, backup retention, monitoring, and secrets.
6. Run `python tools/postgres_preflight.py`.
7. Review stale-evidence counts and unresolved Evidence Lifecycle triggers before migration.

## Migration

```bash
python tools/migrate_sqlite_to_postgres.py \
  --sqlite /secure/path/thira.db \
  --postgres-dsn "$SALUS_DATABASE_URL" \
  --report migration-report.json
```

Primary keys are preserved, PostgreSQL identity sequences are repaired, and source/target row counts are compared. Evidence lifecycle columns migrate with the evidence records.

## Runtime validation

```bash
python tools/postgres_runtime_smoke.py --postgres-dsn "$SALUS_DATABASE_URL"
```

Then start with `SALUS_DB_BACKEND=postgres`, `SALUS_SEED_DEMO=0`, and the approved database identity settings.

## Acceptance checks

- `/health/ready` reports PostgreSQL healthy.
- Tenant and assessment counts match the signed migration report.
- Evidence lifecycle states, validity dates, and open stale-evidence triggers match the source baseline.
- Risk analytics and executive reports match expected pre-cutover values.
- Evidence object hashes match.
- A new portable backup verifies and passes DR validation.
- Session/OIDC, permissions, sensitivity, lifecycle review, audit, and security events work.
