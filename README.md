# Salus THIRA Command v1.17

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.17 adds immutable report snapshots with exact assessment-version and SHA-256 provenance, controlled Draft → Reviewed → Approved → Released authority gates, tenant-isolated audit/version views, and recovery operations that require passed non-destructive validation plus explicit scope, reason, and authorization.

v1.16 activates the governed Executive Decisions and Accepted Risk Workspace. Decisions remain append-only authority records, and accepted risk remains an accountable lifecycle record that can change state only through controlled actions.

## Executive decisions and accepted risk

- Executive decisions use enumerated decision types, a named authority, documented rationale, finite nonnegative funding, and validated dates.
- An Accept Risk decision requires explicit residual exposure, an accountable owner, a reconsideration trigger, and a future review date.
- The decision and its accepted-risk register record are created atomically; neither can persist without the other.
- Accepted-risk provenance and authority are immutable, while descriptive details remain governed and editable.
- Status changes require a controlled transition with a documented authority basis; Closed and Superseded records are terminal.
- Overdue decision and accepted-risk reviews each create one reassessment trigger per lifecycle episode.
- Controlled reviews restore Current lifecycle status and resolve the corresponding trigger without deleting history.
- Closing or superseding an accepted risk resolves its open lifecycle trigger and preserves the full record.
- Every create, automatic lifecycle change, review, and transition is audited and versioned.

## Operational risk and professional judgment

- Inherent and calculated current risk are computed from governed threat, scenario, and capability state.
- Predicted residual risk credits authorized improvements without representing them as demonstrated outcomes.
- Validated residual risk credits only completed improvements supported by Verified, lifecycle-Current evidence.
- Professional assigned risk requires a named authority, documented reason, bounded score, and future review date.
- Optional supporting evidence must belong to the same assessment and be Verified and lifecycle Current.
- Stale, expired, missing, or no-longer-Verified supporting evidence automatically stops the judgment from supplying current assigned risk while leaving calculated risk unchanged.
- An overdue professional review likewise removes current assigned-risk applicability until controlled review.
- Controlled review requires current supporting evidence when the judgment cites evidence.
- A replacement judgment supersedes the prior active judgment without destroying history; controlled withdrawal returns the workspace to calculated risk.
- Client payloads cannot forge calculated values, assigned bands, lifecycle state, authority history, timestamps, audit, or versions.
- Every creation, automatic lifecycle change, review, supersession, and withdrawal is audited and versioned.
- SQLite and PostgreSQL 16 use the same application behavior and validation suite.

## Evidence and risk governance retained

Evidence verification and lifecycle currency remain separate. Evidence may be Verified but Stale. Expired evidence automatically becomes Stale, creates one evidence-lifecycle reassessment trigger per stale episode, loses validated-risk credit, and cannot support a new improvement validation or professional risk override. A controlled lifecycle review is required to restore Current status.

Calculated current risk, professional assigned risk, predicted residual risk, and validated residual risk remain separate governed concepts. Application version: **1.17.0**. Risk methodology version: **1.1.0**.

## Controls retained from prior releases

- assessment, threat/scenario, and target/capability workspaces;
- append-only professional risk overrides and controlled review;
- accepted-risk register and controlled review lifecycle;
- scope lock, scope-change/version history, immutable snapshots, and audit trail;
- direction-aware capability measures and evidence-governed residual-risk validation;
- SQLite local/demo and PostgreSQL native runtime;
- OIDC/session/prototype identity modes;
- tenant/assessment authorization and evidence sensitivity;
- evidence file integrity, retention/legal hold, and upload-scanning hooks;
- Azure Blob/local storage and Key Vault secret-provider paths;
- Redis-capable rate limiting and centralized security telemetry; and
- portable tenant backup, integrity verification, DR validation, and controlled restore.

## Fresh GitHub checkout

The tested source is preserved through the deterministic release archive chain:

```bash
python tools/reconstruct_v117_source.py
python tools/verify_v117_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`, then open `http://127.0.0.1:8000`.

## Release acceptance

The v1.17 release gate requires exact v1.15 → v1.16 reconstruction and SHA-256 verification, Python compilation, JavaScript syntax validation, the SQLite executive-decision and accepted-risk smoke, the identical smoke against real PostgreSQL 16, the PostgreSQL transaction smoke, production-container execution, dependency audit, Bandit, fail-closed CodeQL analysis, release-entrypoint validation, and repository-boundary checks.

## Production status

A frozen application release is not, by itself, authorization to place sensitive client data into production. Production deployment still requires approved identity, managed database and storage, malware scanning, secrets management, network controls, monitoring, records-retention rules, backup/restore procedures, penetration testing, and formal security/privacy review.
