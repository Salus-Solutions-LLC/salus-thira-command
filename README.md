# Salus THIRA Command v1.4.1

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.4.1 is the security patch for the v1.4 evidence-lifecycle release. It preserves v1.4 behavior while preventing diagnostic exception text from reaching external responses or security telemetry, retaining only opaque correlation IDs and exception classes.

v1.4 is the **evidence lifecycle governance release**. It preserves v1.3 professional-risk-override governance while making evidence validity time-aware and fail-closed for risk and validation credit.

## What v1.4 adds

### Evidence validity and lifecycle state

Evidence now records separate verification and lifecycle dimensions:

- `verification_status`: Pending, Verified, or Conflicting;
- `valid_until`: the authoritative validity date when one applies;
- `lifecycle_status`: Current or Stale;
- stale reason and timestamp; and
- lifecycle reviewer and review timestamp.

A record can therefore remain **Verified but Stale**. Verification is not treated as permanent validity.

### Automatic stale-evidence reassessment

When evidence passes its validity date, Salus THIRA Command automatically:

1. marks the evidence Stale;
2. preserves the existing verification status as a separate dimension;
3. creates one open `Evidence Lifecycle / Evidence Stale` reassessment trigger per stale episode;
4. raises trigger severity to High when the evidence supports a validated improvement or active professional risk override, otherwise Moderate;
5. removes stale evidence from validated-residual-risk credit; and
6. prevents stale evidence from supporting a new improvement validation or professional risk override.

Repeated dashboard, evidence, risk, report, export, and backup operations do not create duplicate unresolved stale triggers.

### Controlled lifecycle review

Stale evidence is not returned to Current by an ordinary record edit. A controlled lifecycle-review action requires:

- a current or future new validity date; and
- a documented review outcome.

Verification remains a separate control. A lifecycle review can restore temporal currency without changing Pending, Verified, or Conflicting verification status.

The action records the reviewer/timestamp, clears stale state, resolves the evidence-lifecycle trigger, and writes audit/version history.

### Authoritative outputs refresh lifecycle first

Expiry is refreshed before:

- Risk Analytics;
- Evidence lists;
- Command Center metrics;
- executive reports;
- assessment JSON export; and
- tenant backup capture.

This prevents an expired record from remaining falsely Current merely because an Evidence screen was not opened before an authoritative output was produced.

## Risk governance remains unchanged

Application version: **1.4.1**  
Risk methodology version: **1.1.0**

v1.4 changes evidence governance, not the numerical risk formula. Calculated current risk, professional assigned risk, predicted residual risk, and validated residual risk remain separate governed concepts.

## Controls retained from prior releases

- v1.3 append-only professional risk overrides;
- v1.2 assessment-scoped relational integrity;
- v1.1 evidence-governed residual-risk validation;
- v1.0 direction-aware capability measures;
- Accepted Risk Register;
- scope lock, scope-change/version history, immutable snapshots, and audit trail;
- SQLite local/demo and PostgreSQL native runtime;
- OIDC/session/prototype identity modes;
- tenant/assessment authorization and evidence sensitivity;
- evidence file integrity, retention/legal hold, and upload-scanning hooks;
- Azure Blob/local storage and Key Vault secret-provider paths;
- Redis-capable rate limiting and centralized security telemetry;
- portable tenant backup, integrity verification, DR validation, and controlled restore.

## Fresh GitHub checkout

The tested source is preserved through the deterministic release archive chain:

```bash
python tools/reconstruct_v141_source.py
python tools/verify_v141_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`.

Open `http://127.0.0.1:8000`.

## Release acceptance

The v1.4.1 release gate requires:

- exact source reconstruction and SHA-256 verification;
- Python compilation;
- JavaScript syntax validation;
- SQLite v1.4.1 evidence-lifecycle and security-patch smoke;
- real PostgreSQL 16 v1.4.1 evidence-lifecycle and security-patch smoke;
- PostgreSQL transaction smoke;
- dependency audit;
- Bandit static-security gate; and
- fail-closed local CodeQL Python analysis with SARIF preservation.

## Production status

v1.4.1 is a hardened development/release baseline, not an authorization to place sensitive client data into production by itself. Production deployment still requires approved identity, managed database/storage, malware scanning, secrets management, network controls, monitoring, records-retention rules, backup/restore procedures, penetration testing, and formal security/privacy review.
