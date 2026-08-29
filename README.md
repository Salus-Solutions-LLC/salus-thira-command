# Salus THIRA Command Prototype v0.5

Salus THIRA Command is a database-backed working prototype that operationalizes the Salus THIRA assessment and decision workflow with traceability, governance, evidence integrity, tenant separation, and recovery controls.

## v0.5 highlights

- Server-enforced tenant isolation across dashboards, assessments, records, evidence metadata, reports, audit views, and backups.
- Two authentication modes:
  - `prototype` (default): local role simulation for demonstrations.
  - `session`: server-side users, password hashing, HttpOnly session cookies, tenant identity, role enforcement, and sensitivity clearance.
- Assessment-level access assignments for session users.
- Evidence sensitivity enforcement for Standard, Restricted, Sensitive, and Highly Sensitive records.
- Tenant-specific backup packages containing a consistent SQLite snapshot, only that tenant's evidence attachments, and a SHA-256 integrity manifest.
- Backup verification and audited download.
- Restore is disabled by default and requires `SALUS_ALLOW_RESTORE=1`; full restore is blocked if the database contains more than one tenant.
- Printable server-generated executive HTML report and executive CSV export.
- Existing v0.4 features remain: risk analytics, prioritization, workflow control, scope/version governance, revision history, immutable executive decisions, reassessment triggers, evidence hashes, assessment package export, and multi-assessment selection.

## Reconstruct the tested v0.5 source

GitHub is the authoritative source of truth. Because the connector used to publish the repository has a per-file transfer limit, the two largest tested source files are stored as ordered gzip+Base64 parts under `source_archives/v0.5/`.

From a fresh checkout run:

```bash
python tools/reconstruct_v05_source.py
```

The script reconstructs and verifies:

- `app.py` — SHA-256 `5572cf66373ecf906a1565a6f8d1e10cf3a294e24dbb79550f2cefef86fe06cf`
- `static/app.js` — SHA-256 `1a6dafabb637dc477143c3666d519f4d9d7ebe844fca067ee2566af373f5af8c`

A hash mismatch causes reconstruction to fail rather than silently producing altered source.

## Run locally

### Windows

1. Install Python 3.11 or later.
2. Run `python tools/reconstruct_v05_source.py` after a fresh GitHub checkout.
3. `pip install -r requirements.txt`
4. Run `run_windows.bat`
5. Open `http://127.0.0.1:8000`

### macOS / Linux

1. Install Python 3.11 or later.
2. Run `python tools/reconstruct_v05_source.py` after a fresh GitHub checkout.
3. `pip install -r requirements.txt`
4. Run `./run_mac_linux.sh`
5. Open `http://127.0.0.1:8000`

## Authentication modes

### Prototype mode

Prototype mode is the default and preserves the local role selector used during design and demonstrations.

```text
SALUS_AUTH_MODE=prototype
```

Prototype mode is not security-grade because role identity is simulated by the browser.

### Session mode

Session mode stops trusting browser-supplied role headers and uses server-side users and sessions.

Create the first local administrator before enabling session mode:

```bash
python tools/manage_users.py add marc-admin --display-name "Marc Admin" --role "System Administrator" --clearance "Highly Sensitive" --tenant 1
```

Then start with:

```text
SALUS_AUTH_MODE=session
```

For HTTPS deployments also set:

```text
SALUS_COOKIE_SECURE=1
```

Session lifetime defaults to 12 hours and can be changed with `SALUS_SESSION_HOURS`.

Manage users:

```bash
python tools/manage_users.py list
python tools/manage_users.py disable USERNAME
python tools/manage_users.py grant USERNAME ASSESSMENT_ID
python tools/manage_users.py revoke USERNAME ASSESSMENT_ID
```

If a session user has one or more assessment grants, the portfolio and all record lists are restricted to those assessments.

## Backup and recovery

System Administrators can create and verify backups in **Backup & Recovery**. Packages are stored under `backups/` and are intentionally excluded from Git.

Each backup contains:

- a consistent SQLite database snapshot stripped of other tenants;
- that tenant's evidence attachments only;
- `manifest.json` with SHA-256 hashes and sizes.

Restore is intentionally guarded:

```text
SALUS_ALLOW_RESTORE=1
```

The application creates an automatic pre-restore safety backup. Full restore is blocked when more than one tenant exists because multi-tenant restoration requires a tenant-aware recovery procedure rather than replacing the complete database.

## Executive reporting

Each assessment supports:

- live executive dashboard/report view;
- printable server-generated HTML report suitable for Print / Save PDF;
- executive CSV export;
- complete JSON assessment package export.

## Data and files

- Application database: `thira.db`
- Evidence attachments: `attachments/`
- Backups: `backups/`
- Front end: `static/`
- FastAPI application: `app.py`
- Local session-user administration: `tools/manage_users.py`

## GitHub source-control policy

GitHub is the authoritative home for source code. Do **not** commit:

- `thira.db` or any other live database;
- client evidence or attachments;
- backup packages;
- logs;
- `.env` files;
- credentials, API keys, or secrets.

## Production status

v0.5 materially strengthens the prototype, but it is still not a hardened production deployment. Before storing real sensitive client information in an internet-facing environment, production work still requires enterprise SSO/OIDC integration, TLS termination, managed/encrypted database and object storage, secrets management, malware scanning, retention/legal-hold controls, rate limiting, security monitoring, backup retention/off-site replication, disaster-recovery testing, penetration testing, and formal security/privacy review.

The session framework added in v0.5 is intentionally designed as the bridge to enterprise identity rather than the final SSO implementation.
