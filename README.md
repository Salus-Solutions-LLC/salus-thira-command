# Salus THIRA Command v0.9

Salus THIRA Command is the secure assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v0.9 is the **accepted-risk accountability build**. It preserves the validated v0.8 SQLite/PostgreSQL runtime foundation while making risk acceptance a durable, reviewable governance record rather than a one-time decision label.

## What v0.9 adds

- A dedicated **Accepted Risk Register** tied to the authoritative Executive Decision.
- `Accept Risk` decisions now require a named authority, an explicit residual-exposure statement, and a review date.
- Accepted-risk records are created automatically from authorized decisions; they cannot be deleted.
- Each accepted risk retains the risk statement, decision authority, residual exposure, owner, acceptance date, review date, reconsideration trigger, status, and closure/supersession basis.
- Active and overdue accepted-risk reviews are surfaced on the Command Center.
- Closing an accepted risk requires a documented closure basis; active accepted risks must retain a review date.
- Accepted risk is included in end-to-end traceability, executive CSV/HTML reports, assessment export packages, provider-neutral backups, PostgreSQL migration, and revision history.
- The v0.9 schema migration registry retains the v0.8 baseline and records the v0.9 governance increment.

## v0.8 database-runtime foundation retained

- Native runtime database selection:
  - `SALUS_DB_BACKEND=sqlite` for local demonstrations and lightweight development;
  - `SALUS_DB_BACKEND=postgres` for the managed relational runtime path.
- PostgreSQL compatibility layer for the existing application data-access model:
  - PostgreSQL parameter binding;
  - `BIGSERIAL` identities and `RETURNING id`;
  - PostgreSQL schema inspection in place of SQLite `PRAGMA table_info`;
  - PostgreSQL-safe DDL translation and dependency-aware table creation;
  - identity-sequence repair after explicit-ID migration/restore.
- PostgreSQL runtime health/readiness reporting.
- PostgreSQL connection by DSN or Microsoft Entra / managed identity.
- Controlled SQLite → PostgreSQL migration utility with primary-key preservation and row-count verification.
- PostgreSQL transaction smoke-test utility that rolls test records back.
- Schema migration registry (`schema_migrations`).
- Provider-neutral **portable tenant backups** containing structured records plus evidence objects instead of a copied SQLite database file.
- Portable backup integrity validation and DR validation.
- Tenant-aware portable restore that works without deleting or overwriting other tenants.
- Backward-compatible validation/restoration rules for older v0.7 SQLite backup packages.
- Local Docker Compose PostgreSQL environment for runtime validation on machines with Docker.
- Dedicated PostgreSQL cutover runbook.

All v0.7 controls remain, including OIDC, tenant/assessment authorization, evidence sensitivity, retention/legal hold, malware scanning, Azure Blob support, Key Vault secret resolution, rate limiting, centralized telemetry, backup governance, revision history, scope/workflow governance, risk analytics, prioritization, executive decisions, and reporting.

## Fresh GitHub checkout

The GitHub connector stores the two largest tested source files as verified gzip+base64 archive parts. A fresh clone reconstructs them deterministically:

```bash
python tools/reconstruct_v09_source.py
python tools/verify_v09_source.py
```

The Windows/macOS/Linux launchers and Docker build perform this automatically when the files are absent. Expected SHA-256 values are stored in `source_archives/v0.9/manifest.json`.

## Runtime database modes

### SQLite — local/demo

```text
SALUS_DB_BACKEND=sqlite
SALUS_DB_PATH=./thira.db
SALUS_SEED_DEMO=1
```

SQLite remains the easiest way to run a local demonstration. It is not the preferred multi-user production database.

### PostgreSQL — managed runtime

Password/DSN mode:

```text
SALUS_DB_BACKEND=postgres
SALUS_POSTGRES_AUTH=dsn
SALUS_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
SALUS_SEED_DEMO=0
```

`SALUS_POSTGRES_DSN` can be used as an alias and can be resolved through the existing Key Vault secret provider.

### Azure PostgreSQL with Microsoft Entra / managed identity

```text
SALUS_DB_BACKEND=postgres
SALUS_POSTGRES_AUTH=entra
SALUS_POSTGRES_HOST=server.postgres.database.azure.com
SALUS_POSTGRES_PORT=5432
SALUS_POSTGRES_DATABASE=salus_thira
SALUS_POSTGRES_USER=<database principal configured for the workload identity>
SALUS_POSTGRES_SSLMODE=require
SALUS_SEED_DEMO=0
```

The runtime uses `DefaultAzureCredential` to obtain an Azure Database for PostgreSQL access token. The deployed workload identity must already be authorized inside PostgreSQL.

## SQLite → PostgreSQL migration

First freeze writes and create a v0.9 portable backup. Then migrate into a clean PostgreSQL database:

```bash
python tools/migrate_sqlite_to_postgres.py \
  --sqlite /secure/path/thira.db \
  --postgres-dsn "$SALUS_DATABASE_URL" \
  --report migration-report.json
```

The migration:

- validates SQLite integrity before starting;
- initializes the PostgreSQL schema without demo records;
- preserves application primary keys;
- migrates persistent assessment/governance/security records;
- excludes ephemeral auth sessions and OIDC state;
- excludes old local backup-file metadata and DR validation rows;
- repairs PostgreSQL identity sequences;
- compares source and target row counts;
- fails with a non-zero exit code if verification does not match.

Use `--replace` only during an explicitly authorized target replacement.

For Entra-based PostgreSQL authentication, omit `--postgres-dsn` and provide the `SALUS_POSTGRES_*` environment settings shown above.

Detailed procedure: `deploy/POSTGRESQL_CUTOVER.md`.

## PostgreSQL runtime smoke test

After migration:

```bash
python tools/postgres_runtime_smoke.py --postgres-dsn "$SALUS_DATABASE_URL"
```

The test verifies required tables, inserts a temporary tenant and assessment through the application database adapter, reads them back, and rolls the transaction back.

## Portable backups and recovery

v0.9 backups continue to use `salus-thira-portable-backup-v1`; the records package now includes the Accepted Risk Register when present.

Each backup ZIP contains:

- `records.json` — tenant-scoped application records;
- `attachments/...` — evidence objects referenced by that tenant;
- `manifest.json` — file sizes, SHA-256 hashes, tenant, application version, source database provider, actor, and reason.

This design removes the old assumption that a recoverable backup must contain a SQLite file. The same backup format can be produced from SQLite or PostgreSQL.

The restore path is tenant-aware. It replaces only the selected tenant’s restorable records and evidence objects and preserves other tenants. Restore remains disabled by default and requires:

```text
SALUS_ALLOW_RESTORE=1
```

Enable it only in an approved recovery/maintenance window. Restoring user records invalidates active sessions; administrators should expect to authenticate again afterward.

Older v0.7 SQLite backups can still be integrity/DR validated. Direct legacy SQLite-file restore is available only when SQLite is the active runtime and only when the database is not multi-tenant.

## Local PostgreSQL with Docker

For development/runtime validation on a machine with Docker:

```bash
cp .env.example .env
docker compose -f docker-compose.postgres.yml up --build
```

The compose file launches PostgreSQL 16 and THIRA Command with `SALUS_DB_BACKEND=postgres`. The included default password is **development-only** and must never be used for production.

## Local SQLite run

### Windows

```text
pip install -r requirements.txt
run_windows.bat
```

### macOS / Linux

```bash
pip install -r requirements.txt
./run_mac_linux.sh
```

Then open `http://127.0.0.1:8000`.

## Authentication and security

v0.9 retains three identity modes:

- `prototype` — controlled local demonstration only;
- `session` — local server-side users with HttpOnly sessions;
- `oidc` — enterprise SSO with authorization-code flow, state/nonce validation, JWKS signature validation, issuer/audience validation, and controlled provisioning.

Production should use OIDC plus secure cookies, managed secrets, managed evidence storage, required malware scanning, distributed rate limiting, centralized telemetry, and PostgreSQL.

## Evidence controls

- four sensitivity levels;
- server-side clearance enforcement;
- Azure Blob or local storage adapter;
- SHA-256 integrity verification on every evidence download;
- malware scan/quarantine hook;
- retention-until dates;
- legal holds;
- disposition status;
- audited evidence governance actions.

## Health/readiness

- `GET /health/live`
- `GET /health/ready`

Readiness reports the **actual active runtime database provider**. In production, SQLite remains a blocking readiness issue unless `SALUS_ALLOW_SQLITE_PRODUCTION=1` is explicitly authorized as a temporary exception.

## Source-control policy

GitHub is the authoritative source for code. Never commit:

- live SQLite databases;
- PostgreSQL dumps containing client data;
- migration exports or migration reports containing client records;
- client evidence/uploads;
- backup archives;
- logs;
- `.env` files;
- credentials, tokens, connection strings, or identity-provider secrets.

## v0.9 release validation gates

v0.9 release acceptance is enforced in GitHub Actions against the exact reconstructed source tree. The required gates are:

- deterministic v0.8 → v0.9 source reconstruction with SHA-256 verification of every changed source file;
- Python compilation and JavaScript syntax validation;
- fresh SQLite schema/seed runtime smoke, including both v0.8 and v0.9 migrations;
- Accepted Risk lifecycle smoke: authorized creation, automatic register entry, protected closure, and documented closure basis;
- dependency audit and reviewed medium/high static-security gate;
- a real PostgreSQL 16 service-container run covering schema creation, seeded runtime, v0.9 migration, Accepted Risk table presence, and transaction rollback behavior;
- local CodeQL Python analysis with a fail-closed SARIF findings gate and preserved SARIF artifact.

These automated release gates validate the application/runtime code path. They do not substitute for a production managed-database cutover, tenant-specific Entra configuration, network/security controls, penetration testing, or formal operational authorization.

## Production status

v0.9 retains the v0.8 removal of the application’s architectural dependency on SQLite, but production authorization still requires environment-specific work: a real managed PostgreSQL instance and completed cutover test; Entra/OIDC tenant registration; workload identities and Key Vault permissions; private networking/TLS/WAF; approved Azure storage controls; malware-scanning operations; shared Redis; centralized SIEM routing; CI/security policy enforcement; penetration testing; approved retention schedules; backup/restore exercises; and formal security/privacy approval.
