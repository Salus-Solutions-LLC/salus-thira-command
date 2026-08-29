# Salus THIRA Command v0.7

Salus THIRA Command is the secure assessment and decision-management system for the Salus THIRA methodology. v0.7 extends the working v0.6 application with infrastructure controls intended to support a controlled move from a local prototype into a managed production environment.

## What v0.7 adds

- **Managed secret provider boundary**
  - Environment-variable mode for local development.
  - Azure Key Vault mode using `DefaultAzureCredential` and managed identity-compatible authentication.
  - Environment variables can serve as an authorized emergency/local override without storing secrets in source.
- **Azure Blob passwordless storage option**
  - Preferred production path uses `SALUS_AZURE_STORAGE_ACCOUNT_URL` plus managed identity.
  - Connection-string mode remains available as a fallback and can be resolved through Key Vault.
- **Managed PostgreSQL cutover readiness**
  - `SALUS_MANAGED_DB_TARGET=postgresql` validates the intended PostgreSQL target with `psycopg`.
  - `tools/postgres_preflight.py` performs an explicit connection/readiness check.
  - `tools/export_sqlite_for_postgres.py` creates deterministic NDJSON migration staging files with SHA-256 hashes.
  - The current application runtime still uses SQLite. v0.7 does **not** misrepresent the SQLite query layer as PostgreSQL-compatible. Production readiness is blocked by default until managed-database cutover is completed or a documented exception is authorized.
- **Rate limiting**
  - Single-process memory limiter for local/single-instance operation.
  - Redis-backed distributed limiter for multiple application replicas.
  - 429 responses include request IDs and retry guidance; threshold violations are security events.
- **Centralized security telemetry boundary**
  - Structured JSON events to stdout by default.
  - Optional Azure Monitor / Application Insights OpenTelemetry integration.
  - Database security-event records remain available for tenant-scoped application review.
- **Expanded backup and disaster-recovery validation**
  - Tenant ID is included in backup filenames.
  - Backup sanitization removes other tenants' assessments, users, audit records, security events, DR validation records, sessions, and OIDC state.
  - `DR Validate` performs package hashes, SQLite integrity, required-table checks, recovery-database queries, assessment presence, and evidence attachment-count reconciliation.
  - DR validation results are retained as governed application records.
- **GitHub security gates**
  - CI compilation and JavaScript syntax validation.
  - `pip-audit` dependency scanning.
  - Bandit static security scanning with only the intentional ClamAV subprocess checks excluded.
  - CodeQL advanced workflow using the current major CodeQL action.
- **Production configuration gates** now surface runtime DB, managed DB target, secret backend, rate-limit backend, telemetry backend, storage, malware scanning, OIDC, and secure-cookie readiness.

## Existing application capabilities retained

- Multi-tenant, multi-assessment THIRA workspaces
- Server-side tenant and assessment access enforcement
- OIDC and local authenticated-session modes plus local prototype mode
- Threat/hazard, scenario, consequence, capability, evidence, gap, improvement, decision, implementation, and reassessment workflows
- Transparent inherent/current/estimated residual risk analytics
- Improvement prioritization
- Evidence file integrity, sensitivity, malware scanning, retention, and legal holds
- Version history, scope-change governance, workflow transitions, audit records, security events
- Executive HTML/CSV reporting and portable assessment export
- Tenant-specific backup and guarded restore

## Local run

### Windows

1. Install Python 3.11 or later.
2. `python -m pip install -r requirements.txt`
3. Run `run_windows.bat`.
4. Open `http://127.0.0.1:8000`.

### macOS / Linux

1. Install Python 3.11 or later.
2. `python -m pip install -r requirements.txt`
3. Run `./run_mac_linux.sh`.
4. Open `http://127.0.0.1:8000`.

The GitHub launchers reconstruct and verify the large archived source files automatically when a fresh checkout does not yet contain `app.py` or `static/app.js`.

## Production configuration

Copy `.env.example` only as a reference. Do not commit a populated `.env` file.

Key settings include:

- `SALUS_AUTH_MODE=oidc`
- `SALUS_SECRET_BACKEND=azure_keyvault`
- `SALUS_KEY_VAULT_URL=https://<vault>.vault.azure.net`
- `SALUS_STORAGE_BACKEND=azure`
- `SALUS_AZURE_STORAGE_ACCOUNT_URL=https://<account>.blob.core.windows.net`
- `SALUS_REQUIRE_AV=1`
- `SALUS_RATE_LIMIT_BACKEND=redis`
- `SALUS_REDIS_URL=<protected value>`
- `SALUS_TELEMETRY_BACKEND=azure_monitor`
- `SALUS_MANAGED_DB_TARGET=postgresql`
- `SALUS_POSTGRES_DSN=<protected value or Key Vault reference>`

See `deploy/PRODUCTION_READINESS.md`.

## Managed-database transition

v0.7 separates **runtime truth** from **migration readiness**:

1. Continue operating the validated SQLite application in development/test.
2. Provision and secure the managed PostgreSQL target.
3. Run `python tools/postgres_preflight.py`.
4. Export a deterministic migration package with `python tools/export_sqlite_for_postgres.py --db thira.db --out migration_export`.
5. Validate row counts and SHA-256 manifest.
6. Implement and test PostgreSQL-native schema/query compatibility in a controlled subsequent release.
7. Re-run full tenant, workflow, risk, evidence, backup, and restore regression testing before production cutover.

`SALUS_ALLOW_SQLITE_PRODUCTION=1` exists only as an explicit controlled exception. It should not be treated as normal production architecture.

## Disaster recovery

Application administrators can run two different checks:

- **Verify** — package-level hashes plus SQLite integrity.
- **DR Validate** — performs the verify checks plus recovery-database schema/data checks and evidence-package reconciliation.

CLI validation is also available:

`python tools/dr_validate.py <backup.zip>`

A backup should not be considered recoverable solely because the ZIP exists.

## GitHub source-of-truth

The private GitHub repository is the authoritative source. Stable branches are preserved by version. Because the connector used to publish this build has a per-file transfer ceiling, large `app.py` and `static/app.js` files are preserved in verified compressed source archives. Fresh-clone launchers reconstruct and SHA-256 verify them automatically.

## Production status

v0.7 is a **production-architecture transition build**, not authorization to process sensitive client data in a live environment. Before production, Salus still needs the managed PostgreSQL runtime cutover, real Entra/OIDC tenant configuration, production Key Vault and managed identities, approved Azure storage controls, approved malware-scanning service, Redis or equivalent shared rate-limit state, centralized monitoring/SIEM routing, CI/security policy enforcement, deployment/change management, penetration testing, and documented backup/restore exercises.
