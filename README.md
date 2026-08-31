# Salus THIRA Command v1.14

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.14 activates the governed Gap and Improvement Workspace. Capability gaps and improvement actions are assessment-scoped, tenant-isolated, audited, versioned, and connected to evidence-based capability validation.

## Gap and improvement governance

- Every gap references a capability in the same assessment.
- Gap type, severity, description, root cause, owner, and lifecycle state use bounded governed fields.
- Every improvement references a gap in the same assessment.
- Cost, schedule, feasibility, consequence reduction, mission benefit, sustainability, compliance, staffing, dependencies, expected capability gain, and owner are retained as authoritative inputs.
- Priority scores are calculated by the server from the recorded factors and cannot be supplied or overwritten by clients.
- New gaps start Open and new improvements start Proposed with Pending validation.
- Gap and improvement lifecycle state changes require controlled transition actions with documented reasons.
- Completing an improvement creates one Capability Validation reassessment trigger without duplication.
- Controlled validation requires Verified evidence whose lifecycle is Current and records the accountable validator, evidence, outcome, effectiveness, timestamp, audit event, and immutable version.
- Generic edits cannot forge lifecycle, validation, priority, tenant, timestamp, audit, or version state.
- SQLite and PostgreSQL 16 use the same application behavior and validation suite.

## Evidence and risk governance retained

Evidence verification and lifecycle currency remain separate. Evidence may be Verified but Stale. Expired evidence automatically becomes Stale, creates one evidence-lifecycle reassessment trigger per stale episode, loses validated-risk credit, and cannot support a new improvement validation or professional risk override. A controlled lifecycle review is required to restore Current status.

Calculated current risk, professional assigned risk, predicted residual risk, and validated residual risk remain separate governed concepts. Application version: **1.14.0**. Risk methodology version: **1.1.0**.

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
python tools/reconstruct_v114_source.py
python tools/verify_v114_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`, then open `http://127.0.0.1:8000`.

## Release acceptance

The v1.14 release gate requires exact v1.13 → v1.14 reconstruction and SHA-256 verification, Python compilation, JavaScript syntax validation, the SQLite lifecycle smoke, the identical smoke against real PostgreSQL 16, the PostgreSQL transaction smoke, production-container execution, dependency audit, Bandit, fail-closed CodeQL analysis, release-entrypoint validation, and repository-boundary checks.

## Production status

A frozen application release is not, by itself, authorization to place sensitive client data into production. Production deployment still requires approved identity, managed database and storage, malware scanning, secrets management, network controls, monitoring, records-retention rules, backup/restore procedures, penetration testing, and formal security/privacy review.
