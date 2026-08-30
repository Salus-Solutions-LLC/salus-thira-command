# PostgreSQL Cutover Runbook — Salus THIRA Command v1.4

v1.4 supports two runtime database providers: `sqlite` and `postgres`. A production cutover should be treated as a controlled change, not an in-place experiment.

## Preconditions

1. Freeze writes to the source SQLite environment.
2. Create and DR-validate a v1.4 portable tenant backup.
3. Verify the source SQLite database with `PRAGMA integrity_check`.
4. Provision the PostgreSQL target with TLS required and an approved identity model.
5. Configure network restrictions, backup retention, monitoring, and secrets before migration.
6. Run `python tools/postgres_preflight.py` against the target.

## Migration

Use a clean PostgreSQL database unless an authorized replacement is intended:

```bash
python tools/migrate_sqlite_to_postgres.py \
  --sqlite /secure/path/thira.db \
  --postgres-dsn "$SALUS_DATABASE_URL" \
  --report migration-report.json
```

The migration preserves primary keys, repairs PostgreSQL identity sequences, and compares source and target row counts. Ephemeral login sessions, OIDC state, local backup-file metadata, and DR validation rows are intentionally not migrated.

## Runtime validation

```bash
python tools/postgres_runtime_smoke.py --postgres-dsn "$SALUS_DATABASE_URL"
```

The smoke test creates records inside a transaction, reads them through the application adapter, and rolls the transaction back.

Then start the application with:

```text
SALUS_DB_BACKEND=postgres
SALUS_DATABASE_URL=...
SALUS_SEED_DEMO=0
```

For Azure Database for PostgreSQL with Microsoft Entra authentication, use `SALUS_POSTGRES_AUTH=entra` plus the host/database/user settings in `.env.example` and grant the workload managed identity database access.

## Acceptance checks

- `/health/ready` reports PostgreSQL as the active healthy runtime database.
- Tenant and assessment counts match the signed migration report.
- Risk analytics and executive reports match the pre-cutover baseline.
- Evidence metadata and stored-object hashes match.
- A new portable backup verifies and passes DR validation after cutover.
- Session/OIDC login, role permissions, sensitivity controls, and audit/security events work.
- Rollback criteria and the pre-cutover backup remain available until formal acceptance.
