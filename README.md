# Salus THIRA Command v1.10

Salus THIRA Command is the assessment, capability, evidence, governance, executive decision-management, and governed intake system for the Salus THIRA methodology.

v1.10 activates a governed operational Assessment Workspace. Authenticated users can create tenant-isolated Member Client assessments with persisted scope context, server-controlled Draft and lifecycle state, atomic audit/version history, and portable backup coverage. Generic client input cannot forge tenant, status, lifecycle, reviewer, version, creator, scope lock, or timestamps.

v1.9 governed intake remains operational. Evidence lifecycle, validated-risk credit, professional risk overrides, accepted risks, executive decisions, reassessment governance, traceability, security controls, and portable recovery remain regression-gated.

## Fresh GitHub checkout

The tested source is preserved through the deterministic release archive chain:

```bash
python tools/reconstruct_v110_source.py
python tools/verify_v110_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`. Open `http://127.0.0.1:8000`.

## Release acceptance

The v1.10 gate requires exact source reconstruction, Python and JavaScript checks, SQLite lifecycle regression, real PostgreSQL 16 lifecycle regression, PostgreSQL transaction validation, production-container tests, dependency audit, Bandit, fail-closed CodeQL analysis, release entrypoint validation, and repository-boundary checks.

## Production boundary

A frozen application release is not by itself authorization to place sensitive Member Client data into production. Production use still requires approved identity, managed database and storage, malware scanning, secrets management, network controls, monitoring, retention, backup/restore, penetration testing, and formal security/privacy approval.
