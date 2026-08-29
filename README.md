# Salus THIRA Command v0.6

Salus THIRA Command is the database-backed Salus assessment and decision-management system. v0.6 advances the v0.5 multi-tenant prototype toward deployable production architecture while preserving local demonstration and test operation.

## v0.6 highlights

- Three identity modes:
  - `prototype` for controlled local demonstrations;
  - `session` for local server-side users and HttpOnly sessions;
  - `oidc` for enterprise SSO through an OpenID Connect provider.
- OIDC authorization-code flow with state and nonce validation, JWKS signature verification, issuer/audience verification, pre-provisioned users, and optional controlled auto-provisioning.
- Server-enforced tenant and assessment access continues across portfolio, records, evidence, reports, backups, and audit/security views.
- Evidence storage abstraction:
  - local filesystem for development;
  - Azure Blob Storage for managed evidence storage.
- Pre-storage malware scanning hook using ClamAV.
- Optional fail-closed upload policy with `SALUS_REQUIRE_AV=1`.
- Evidence SHA-256 is verified again on every download; a mismatch is blocked and logged as a critical security event.
- Evidence retention dates, legal holds, and disposition status.
- Server prevents evidence deletion while legal hold is active or the retention period has not expired.
- Security event register for authentication failures, authorization-boundary events, rejected uploads, hash mismatches, storage failures, and unhandled server errors.
- Request IDs and baseline HTTP security headers.
- `/health/live` and `/health/ready` endpoints.
- Production-readiness checks that reject insecure production configuration.
- Dockerfile and Docker Compose deployment scaffolding.
- v0.5 capabilities remain: risk analytics, prioritization, tenant-scoped verified backups, recovery safeguards, executive reports, workflow/scope governance, evidence sensitivity, reassessment triggers, and revision history.

## Fresh GitHub checkout

The GitHub connector stores the two largest tested source files as verified gzip+base64 archive parts. A fresh clone can reconstruct them deterministically:

```bash
python tools/reconstruct_v06_source.py
python tools/verify_v06_source.py
```

`run_windows.bat`, `run_mac_linux.sh`, and the Docker build perform this reconstruction/verification automatically when needed. The expected SHA-256 values are recorded in `source_archives/v0.6/manifest.json`.

## Run locally

### Windows

1. Install Python 3.11 or later.
2. `pip install -r requirements.txt`
3. Run `run_windows.bat`
4. Open `http://127.0.0.1:8000`

### macOS / Linux

1. Install Python 3.11 or later.
2. `pip install -r requirements.txt`
3. Run `./run_mac_linux.sh`
4. Open `http://127.0.0.1:8000`

On first run the application creates the SQLite database and fictional demonstration assessment.

## Identity modes

### Prototype

```text
SALUS_AUTH_MODE=prototype
```

This is for local development/demonstration only. Browser role headers are intentionally trusted in this mode.

### Local session

```text
SALUS_AUTH_MODE=session
SALUS_COOKIE_SECURE=1   # for HTTPS deployments
```

Create a user:

```bash
python tools/manage_users.py add marc-admin --display-name "Marc Admin" --email "user@example.com" --role "System Administrator" --clearance "Highly Sensitive"
```

### Enterprise OIDC / SSO

```text
SALUS_AUTH_MODE=oidc
SALUS_OIDC_DISCOVERY_URL=https://identity-provider.example/.well-known/openid-configuration
SALUS_OIDC_CLIENT_ID=...
SALUS_OIDC_CLIENT_SECRET=...
SALUS_OIDC_REDIRECT_URI=https://thira.example.com/api/auth/oidc/callback
SALUS_OIDC_DEFAULT_TENANT_SLUG=salus-prototype
SALUS_OIDC_AUTO_PROVISION=0
SALUS_COOKIE_SECURE=1
```

For pre-provisioned accounts, create the user and bind the external subject:

```bash
python tools/manage_users.py add user@example.com --display-name "Example User" --email "user@example.com" --role "Lead Assessor" --clearance "Sensitive"
python tools/manage_users.py bind-oidc user@example.com --subject "OIDC-SUBJECT" --provider oidc --email "user@example.com"
```

Automatic provisioning is disabled by default. When enabled, new OIDC users enter as `Contributor` with `Standard` clearance in the configured default tenant.

## Evidence storage

### Local development

```text
SALUS_STORAGE_BACKEND=local
SALUS_LOCAL_STORAGE_DIR=./attachments
```

### Azure Blob Storage

```text
SALUS_STORAGE_BACKEND=azure
SALUS_AZURE_STORAGE_CONNECTION_STRING=...
SALUS_AZURE_STORAGE_CONTAINER=salus-thira-evidence
```

The application stores only the object key in the assessment database. Backup creation reads through the storage adapter, so the same backup process works with local or Azure-backed evidence.

## Malware scanning

For ClamAV:

```text
SALUS_AV_MODE=clamav
SALUS_REQUIRE_AV=1
SALUS_CLAMSCAN_PATH=clamscan
```

The file is held in a temporary quarantine file for scanning before it is promoted into evidence storage. An infected file or required-but-unavailable scanner causes the upload to fail.

Development mode can leave scanning off:

```text
SALUS_AV_MODE=off
SALUS_REQUIRE_AV=0
```

## Retention and legal hold

New evidence attachments receive a default retention-until date based on:

```text
SALUS_RETENTION_DEFAULT_DAYS=2555
```

Authorized decision users can modify the date or place/release a legal hold. The server blocks deletion when either a legal hold is active or the retention-until date remains in the future.

## Security telemetry

System Administrators can review **Security & Readiness** in the application. Events include:

- login failures and OIDC failures;
- tenant/assessment authorization failures;
- upload rejection or unavailable malware scanner;
- evidence SHA-256 mismatch;
- storage failures;
- unhandled application errors.

Every HTTP response receives an `X-Request-ID` for correlation.

## Health and readiness

- `GET /health/live` confirms the process is running.
- `GET /health/ready` verifies database/storage access and checks production configuration.

When `SALUS_ENV=production`, readiness fails if production requirements are not met, including non-prototype authentication and secure cookies. Local evidence storage and disabled upload scanning are also surfaced as production readiness problems.

## Docker

Copy `.env.example` to `.env`, set the required values, then:

```bash
docker compose up --build
```

The container runs as a non-root user and includes a readiness health check.

## Source-control policy

GitHub is the authoritative source for code. Do **not** commit:

- live `thira.db` / SQLite files;
- client evidence or uploaded files;
- backup archives;
- logs;
- `.env` or secrets;
- identity-provider client secrets or Azure storage credentials.

## v0.6 regression validation

The clean build was tested for:

- prototype startup and health/readiness;
- local session login and failed-login security events;
- OIDC fail-closed behavior when provider configuration is incomplete;
- tenant-boundary denial and security-event creation;
- attachment upload, scan state, retention assignment, and SHA-256 download verification;
- legal-hold and retention-based deletion denial;
- evidence hash-tampering detection;
- backup creation and integrity verification through the storage abstraction;
- required-malware-scanner fail-closed behavior;
- production readiness rejecting insecure defaults;
- Python compilation and JavaScript syntax validation.

## Production status

v0.6 is substantially closer to a deployable architecture, but it is still not authorization to place real client-sensitive data on an internet-facing production service. Remaining production work includes a managed relational database, production TLS/ingress, provider-specific SSO registration and claims mapping, secrets vault integration, Azure/private-network architecture, off-site backup replication and restore drills, centralized security monitoring/SIEM, malware-engine operations, retention schedules approved by counsel/records management, rate limiting/WAF, vulnerability scanning, penetration testing, and formal security/privacy review.
