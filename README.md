# Salus THIRA Command v1.1

Salus THIRA Command is the assessment, capability, evidence, governance, and executive decision-management system for the Salus THIRA methodology.

v1.1 is the **governed residual-risk baseline**. It preserves the validated v1.0 capability measurement framework while separating forecast risk reduction from evidence-validated risk reduction.

## Governed risk states

THIRA Command now distinguishes four states instead of treating an approved action as achieved risk reduction:

1. **Inherent Risk** — likelihood × vulnerability/exposure × modeled consequence before capability credit.
2. **Current Risk** — inherent risk adjusted only for demonstrated current capability.
3. **Predicted Residual Risk** — a planning forecast that may credit the expected benefit of currently approved improvements. It is explicitly not treated as achieved.
4. **Validated Residual Risk** — improvement benefit is credited only after the improvement is Complete and a controlled validation cites evidence whose verification status is currently `Verified`.

Executive approval by itself never lowers Current Risk or Validated Residual Risk. Marking an improvement Complete also does not lower Validated Residual Risk.

If cited validation evidence is later downgraded from `Verified`, the associated validated risk-reduction credit disappears automatically. A later executive decision such as Defer or Reject also prevents an older approval from continuing to supply forecast or validated credit.

## Improvement validation

A completed improvement can be validated as:

- `Validated`
- `Partially Validated`
- `Failed`

Validation requires:

- a completed improvement;
- a verified evidence record from the same assessment;
- a documented validation outcome;
- an explicit validated-effectiveness percentage;
- an accountable validating user and timestamp.

Failed validation earns zero risk-reduction credit and automatically opens a corrective-action reassessment trigger. Validation records are revisioned and audited. Direct edits to validation state are blocked; the controlled validation action must be used.

## Risk methodology versioning

Each assessment consequence-weight record now carries `risk_methodology_version`. v1.1 risk outputs and exports identify the methodology used, allowing later scoring-method changes to remain distinguishable from historical results.

## v1.0 capabilities retained

The Capability Measurement Framework supports Percentage, Time, Count, Rate, Binary, Currency, and Qualitative Rubric measures with `>=`, `<=`, or exact `=` target semantics. Raw target/current measures remain visible while normalized attainment allows unlike capabilities to be compared consistently.

The Accepted Risk Register remains durable and non-deletable until formally closed or superseded with documented authority and basis.

## Runtime and security controls retained

- SQLite local/demo and PostgreSQL managed-runtime paths;
- Microsoft Entra/managed-identity PostgreSQL authentication hooks;
- OIDC/session/prototype identity modes;
- tenant and assessment authorization;
- evidence sensitivity, SHA-256 integrity, retention/legal hold, and upload scanning hooks;
- Azure Blob/local storage abstraction;
- Key Vault secret-provider path;
- Redis-capable distributed rate limiting;
- centralized security telemetry;
- portable tenant backup, integrity verification, DR validation, and controlled restore;
- scope/workflow governance, revision history, executive decisions, Accepted Risk, and reporting.

## Fresh GitHub checkout

The largest tested source files are preserved through a deterministic, SHA-256 verified delta chain:

```bash
python tools/reconstruct_v11_source.py
python tools/verify_v11_source.py
```

The v1.1 reconstruction establishes the exact v1.0 baseline first, applies the v1.1 delta, and verifies the resulting hashes. Windows/macOS/Linux launchers and Docker perform this automatically when required.

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

## Release validation gates

v1.1 acceptance is fail-closed against the exact reconstructed source tree:

- SHA-256 source reconstruction and verification;
- Python compilation and JavaScript syntax validation;
- shared lifecycle smoke against SQLite and PostgreSQL 16;
- proof that approval changes only Predicted Residual, not Current/Validated Residual;
- proof that completion alone earns no validated risk reduction;
- verified-evidence requirement for controlled improvement validation;
- partial/full/failed validation behavior;
- automatic loss of validated credit if supporting evidence ceases to be Verified;
- latest executive-decision control over forecast credit;
- v1.0 capability measurement semantics;
- Accepted Risk governance;
- PostgreSQL transaction rollback smoke;
- dependency audit and reviewed Bandit gate;
- local Python CodeQL analysis with fail-closed SARIF findings enforcement.

These gates validate application/runtime behavior. They do not substitute for production managed-database cutover, tenant-specific Entra configuration, private networking/WAF/TLS, penetration testing, backup exercises, retention approval, or formal security/privacy authorization.

GitHub remains authoritative for code. Never commit live client databases, evidence/uploads, backups, logs, `.env` files, credentials, tokens, connection strings, or identity-provider secrets.
