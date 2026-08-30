# Salus THIRA Command v1.2

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.2 is the **relational-integrity release**. It preserves the governed residual-risk model introduced in v1.1 while ensuring that linked assessment records cannot silently cross assessment boundaries.

## What v1.2 adds

### Assessment-scoped relationship enforcement

The server now validates the principal THIRA chain before creates and updates are committed:

- Scenario → Threat / Hazard
- Capability → Scenario (optional)
- Evidence → Capability (optional)
- Evidence → Scenario (optional)
- Gap → Capability
- Improvement → Gap
- Executive Decision → Improvement (optional)
- Reassessment Trigger → affected governed record, when an affected record ID is supplied

A related record must exist and belong to the same assessment. Cross-assessment links fail closed with a validation error instead of relying on ordinary foreign keys, which only prove that an ID exists.

### Immutable assessment ownership

Once a governed child record is created, its `assessment_id` cannot be changed through the generic update API. If a record belongs in another assessment, a new governed record must be created there rather than moving history between assessment workspaces.

This protects audit history, entity-version snapshots, traceability, reports, Accepted Risk, residual-risk calculations, and tenant/assessment authorization semantics.

### Assessment-scoped selectors in the interface

Users no longer type the principal relationship IDs into normal data-entry forms. The active assessment supplies the assessment identity automatically, and related records are presented as assessment-scoped selectors:

- Threat / Hazard names for scenarios
- Scenario titles for capabilities and evidence
- Capability names for evidence and gaps
- Gap severity/description for improvements
- Improvement titles for executive decisions

Numeric IDs remain available where they are useful for audit, traceability, exports, and technical record identification, but they are no longer the normal relationship-entry mechanism.

## Risk methodology remains v1.1

v1.2 changes application integrity, not the risk formula. `risk_methodology_version` therefore remains **1.1.0**.

The governed risk states remain:

1. **Inherent Risk** — before capability credit.
2. **Current Risk** — adjusted only for demonstrated current capability.
3. **Predicted Residual Risk** — planning forecast that may credit currently approved improvements.
4. **Validated Residual Risk** — improvement benefit credited only after completed implementation and controlled validation backed by currently Verified evidence.

Approval or completion alone does not lower validated risk. Evidence downgrade revokes validated credit, and the latest executive decision controls forecast eligibility.

## Capability measurement framework retained

The v1.0 framework remains available for Percentage, Time, Count, Rate, Binary, Currency, and Qualitative Rubric measures using `>=`, `<=`, or exact `=` target semantics.

## Runtime and governance controls retained

- SQLite local/demo and PostgreSQL managed-runtime paths;
- Microsoft Entra/OIDC/session/prototype identity modes;
- tenant and assessment authorization;
- scope lock, authorized scope-change records, assessment version increments, and immutable entity snapshots;
- evidence sensitivity, SHA-256 integrity, retention/legal hold, and upload scanning hooks;
- Accepted Risk Register and controlled closure/supersession;
- evidence-backed improvement validation;
- Azure Blob/local storage abstraction;
- Key Vault secret-provider path;
- Redis-capable distributed rate limiting;
- centralized security telemetry;
- portable tenant backup, integrity verification, DR validation, and controlled restore.

## Fresh GitHub checkout

The largest tested source files are preserved through a deterministic SHA-256 verified delta chain:

```bash
python tools/reconstruct_v12_source.py
python tools/verify_v12_source.py
```

The v1.2 reconstruction establishes the exact frozen v1.1 baseline, applies the v1.2 delta, and verifies the resulting hashes. Windows/macOS/Linux launchers and Docker perform this automatically when source reconstruction is required.

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

## v1.2 release validation gates

Release acceptance is fail-closed against the exact reconstructed source tree:

- deterministic v1.1 → v1.2 source reconstruction with SHA-256 verification;
- Python compilation and JavaScript syntax validation;
- application migration marker `1.2.0` while risk methodology remains `1.1.0`;
- retained v1.0 direction-aware capability semantics;
- retained v1.1 governed residual-risk lifecycle;
- valid same-assessment Threat → Scenario → Capability → Gap → Improvement → Decision chain;
- rejection of cross-assessment Scenario/Threat, Gap/Capability, Improvement/Gap, Decision/Improvement, Evidence/Capability, Evidence/Scenario, and reassessment-trigger links;
- rejection of cross-assessment child-record reassignment;
- revalidation of relationships on update, not only create;
- assessment-scoped list isolation and UI relationship-selector checks;
- the same lifecycle smoke against SQLite and a real PostgreSQL 16 service container;
- PostgreSQL transaction rollback smoke;
- dependency audit and reviewed Bandit gate;
- local Python CodeQL analysis with fail-closed SARIF findings enforcement.

These automated gates validate application/runtime behavior. They do not substitute for a production managed-database cutover, tenant-specific Entra configuration, private networking/WAF/TLS, penetration testing, backup/restore exercises, records-retention approval, or formal security/privacy authorization.

GitHub remains authoritative for code. Never commit live client databases, evidence/uploads, backups, logs, `.env` files, credentials, tokens, connection strings, or identity-provider secrets.
