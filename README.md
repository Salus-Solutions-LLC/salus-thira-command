# Salus THIRA Command v1.11

Salus THIRA Command is the assessment, capability, evidence, governance, executive decision-management, and governed intake system for the Salus THIRA methodology.

v1.11 activates governed Threat & Scenario workspaces. Authenticated users can create tenant-isolated threat/hazard records inside a Member Client assessment and connect contextual scenarios only to threats in that same assessment. Scores and enumerated governance fields are bounded, state is server-controlled, and every creation produces audit and immutable version history.

v1.10 assessment workspaces and v1.9 governed intake remain operational. Evidence lifecycle, validated-risk credit, professional risk overrides, accepted risks, executive decisions, reassessment governance, traceability, security controls, and portable recovery remain regression-gated.

## Fresh GitHub checkout

```bash
python tools/reconstruct_v111_source.py
python tools/verify_v111_source.py
```

Windows and macOS/Linux launchers perform reconstruction and verification automatically when needed.

## Run locally

```bash
python -m pip install -r requirements.txt
./run_mac_linux.sh
```

On Windows, use `run_windows.bat`. Open `http://127.0.0.1:8000`.

## Release acceptance

The v1.11 gate requires exact source reconstruction, Python and JavaScript checks, SQLite regression, real PostgreSQL 16 regression, PostgreSQL transaction validation, production-container tests, dependency audit, Bandit, fail-closed CodeQL analysis, release entrypoint validation, and repository-boundary checks.

## Production boundary

A frozen application release is not by itself authorization to place sensitive Member Client data into production. Production use still requires approved identity, managed database and storage, malware scanning, secrets management, network controls, monitoring, retention, backup/restore, penetration testing, and formal security/privacy approval.
