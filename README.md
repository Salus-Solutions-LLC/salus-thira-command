# Salus THIRA Command v1.3

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.3 is the **professional-risk-override governance release**. It preserves all v1.2 relational-integrity controls while separating calculated risk from accountable professional judgment.

## What v1.3 adds

### Professional Risk Override Register

A professional judgment no longer overwrites a calculated risk value. Instead, the system records a governed override containing:

- assessment and threat/hazard identity;
- calculated current-risk score and band at the time of judgment;
- assigned professional-risk score and derived band;
- documented reason / professional basis;
- named authority;
- optional supporting Verified evidence from the same assessment;
- review date;
- creator and timestamp;
- supersession linkage; and
- governed withdrawal reason, actor, and timestamp.

Only roles with decision authority may create or withdraw a professional risk override.

### Append-only professional judgment history

A new professional judgment supersedes the prior active override rather than rewriting it. Withdrawal also preserves the prior record. Direct generic updates and deletes are not permitted for risk overrides.

The full history is included in:

- Risk Analytics;
- traceability;
- executive CSV and printable HTML reports;
- assessment JSON exports;
- tenant backup / restore packages;
- entity-version snapshots; and
- audit records.

### Risk mathematics remain governed

v1.3 does **not** change the risk formula. The methodology version remains **1.1.0**.

The system continues to distinguish:

1. **Inherent Risk** — before capability credit.
2. **Calculated Current Risk** — adjusted only for demonstrated current capability.
3. **Professional Assigned Risk** — accountable judgment recorded separately from the calculation.
4. **Predicted Residual Risk** — forecast benefit from currently approved improvements.
5. **Validated Residual Risk** — benefit credited only after completed implementation and controlled validation backed by currently Verified evidence.

Professional assigned risk does not alter predicted or validated residual-risk mathematics.

## Controls retained from prior releases

- v1.2 assessment-scoped relational integrity and immutable child-record ownership;
- v1.1 evidence-governed residual-risk validation;
- v1.0 direction-aware capability measures (`>=`, `<=`, `=`);
- Accepted Risk Register;
- scope lock, controlled scope changes, assessment version increments, and immutable entity snapshots;
- SQLite local/demo and PostgreSQL native runtime;
- OIDC/session/prototype identity modes;
- tenant and assessment authorization;
- evidence sensitivity, SHA-256 integrity, retention/legal hold, and upload scanning hooks;
- Azure Blob/local storage abstraction;
- Key Vault secret-provider path;
- Redis-capable distributed rate limiting;
- centralized security telemetry;
- portable tenant backup, integrity verification, DR validation, and controlled restore.

## Fresh GitHub checkout

The largest tested source files are preserved through a deterministic SHA-256 verified delta chain:

```bash
python tools/reconstruct_v13_source.py
python tools/verify_v13_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`.

Then open `http://127.0.0.1:8000`.

## Release acceptance

The v1.3 release gate requires:

- exact source reconstruction and SHA-256 verification;
- Python compilation;
- JavaScript syntax validation;
- SQLite v1.3 lifecycle smoke;
- real PostgreSQL 16 v1.3 lifecycle smoke;
- PostgreSQL transaction smoke;
- dependency audit;
- Bandit static-security gate; and
- fail-closed local CodeQL Python analysis with SARIF preservation.

## Production status

v1.3 is a hardened development/release baseline, not an authorization to place sensitive client data into production by itself. Production deployment still requires approved managed identity, database, object storage, malware scanning, secrets management, network controls, monitoring, retention rules, backup/restore procedures, penetration testing, and formal security/privacy review.
