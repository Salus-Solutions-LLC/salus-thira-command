# Salus THIRA Command v1.0

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.0 is the **capability-measurement and accountable-risk baseline**. It preserves the validated v0.9 multi-tenant, security, evidence, PostgreSQL, backup/recovery, and Accepted Risk controls while correcting a foundational modeling problem: capability performance no longer assumes that a larger number is always better.

## What v1.0 adds

The Capability Measurement Framework now supports:

- **Percentage**
- **Time**
- **Count**
- **Rate**
- **Binary**
- **Currency**
- **Qualitative Rubric**

Each capability records a measurement type, unit, target comparator (`>=`, `<=`, or exact `=`), required standard, current demonstrated performance, evidence confidence, and validation dates.

Examples:

- Target `<= 10 minutes`, actual `8 minutes` → **100% attained**.
- Target `<= 10 minutes`, actual `12 minutes` → **83.3% attained**, physical gap **2 minutes**.
- Target `>= 95%`, actual `72%` → **75.8% attained**.
- Binary target `1`, current `1` → **100% attained**.

The application keeps the raw target/current values visible. Normalized attainment is used only to compare unlike capability measures consistently for dashboards and risk analytics.

## Governance retained

v1.0 retains the v0.9 **Accepted Risk Register**. An `Accept Risk` executive decision requires a named authority, explicit residual exposure, and review date. The resulting accepted-risk record remains active, owned, traceable, reviewable, and non-deletable until formally closed or superseded with a documented basis.

Other retained controls include:

- assessment scope lock and controlled scope changes;
- workflow transitions and revision snapshots;
- tenant and assessment access enforcement;
- evidence sensitivity, file hashes, retention, legal hold, and upload-scanning hooks;
- OIDC/session/prototype identity modes;
- rate limiting and centralized security telemetry;
- portable tenant backup, integrity verification, DR validation, and controlled restore;
- SQLite and PostgreSQL runtime support;
- Azure Key Vault / managed identity integration hooks;
- Azure Blob or local evidence storage.

## Database runtimes

### SQLite — local/demo

```text
SALUS_DB_BACKEND=sqlite
SALUS_DB_PATH=./thira.db
SALUS_SEED_DEMO=1
```

### PostgreSQL — managed runtime path

```text
SALUS_DB_BACKEND=postgres
SALUS_POSTGRES_AUTH=dsn
SALUS_DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require
SALUS_SEED_DEMO=0
```

Azure Database for PostgreSQL can use Microsoft Entra / managed identity via the `SALUS_POSTGRES_*` environment settings documented in `.env.example` and `deploy/POSTGRESQL_CUTOVER.md`.

## Fresh GitHub checkout

Large source files are stored through a deterministic, SHA-256 verified delta chain. A fresh checkout reconstructs the exact v1.0 application source with:

```bash
python tools/reconstruct_v10_source.py
python tools/verify_v10_source.py
```

Windows/macOS/Linux launchers and the Docker build perform this verification automatically. Expected v1.0 file hashes are stored in `source_archives/v1.0/manifest.json`.

## Run locally

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

## Portable backup and recovery

Portable tenant backups use `salus-thira-portable-backup-v1` and contain structured tenant records, referenced evidence objects, and a SHA-256 manifest. v1.0 capability measurement fields and Accepted Risk records are included automatically with their source records.

Restore is disabled by default and requires `SALUS_ALLOW_RESTORE=1` during an approved recovery window.

## Health/readiness

- `GET /health/live`
- `GET /health/ready`

Production readiness remains fail-closed when SQLite is active unless an explicit temporary exception is authorized.

## Release validation gates

v1.0 acceptance is enforced against the exact reconstructed source tree in GitHub Actions:

- SHA-256 source reconstruction and verification;
- Python compilation and JavaScript syntax validation;
- the same release lifecycle smoke against **SQLite and PostgreSQL 16**;
- capability measurement tests covering higher-is-better, lower-is-better, binary validation, derived attainment/gap/status, dashboard output, traceability, and executive reports;
- Accepted Risk creation, protected closure, and documented closure basis;
- PostgreSQL transaction rollback smoke;
- dependency audit;
- reviewed medium/high Bandit security gate;
- local Python CodeQL analysis with fail-closed SARIF findings enforcement.

These automated gates validate the application/runtime code path. They do not substitute for a production managed-database cutover, tenant-specific Entra configuration, private networking/WAF/TLS, penetration testing, backup exercises, records-retention approval, or formal security/privacy authorization.

## Source-control policy

GitHub is authoritative for code. Never commit live client databases, PostgreSQL dumps with client data, evidence/uploads, backup archives, logs, `.env` files, credentials, tokens, connection strings, or identity-provider secrets.

See `RELEASE_NOTES_v1.0.md`, `deploy/PRODUCTION_READINESS.md`, and `deploy/POSTGRESQL_CUTOVER.md` for additional detail.
