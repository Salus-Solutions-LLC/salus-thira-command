# SalCAPA v3.0

SalCAPA is Salus Solutions' secure intelligence, risk, and operations platform.

## Product structure

- **SalCAPA** provides the role-aware Common Operating Picture for Protected Members and authorized Salus personnel.
- **SalINTEL** collects, qualifies, validates, analyzes, and monitors intelligence.
- **SalTHIRA** identifies threats and hazards, establishes context and capability targets, assesses capabilities, identifies gaps, and supports risk and impact decisions.
- **SalOPS** governs approved requests, authorization, assignment, operations, results, and feedback.

Shared platform controls provide tenant isolation, identity and authorization, a governed See–Coordinate–Act Common Operating Picture, member decision requests, governed observation intake and triage, evidence lifecycle governance, reassessment triggers, professional judgment, Protected Member executive authority, accepted risk, immutable reporting, audit/version history, backup, governed recovery, a versioned SalOPS service catalog, readiness-gated engagement orchestration, governed expert qualification and assignment, tenant-scoped versioned industry profiles, governed estimates and actual expenses, and invoice-ready operational statements.

## Development and release controls

GitHub is authoritative. Development occurs on governed development branches. Every release candidate must pass deterministic reconstruction, SQLite, PostgreSQL 16, production-container, dependency audit, Bandit, repository hygiene, and CodeQL gates. Validation pull requests are closed without merge. Frozen release branches are immutable.

Reconstruct and verify this candidate with:

```bash
python tools/reconstruct_v30_source.py
python tools/verify_v30_source.py
```

Run the complete SalCAPA governed-workflow smoke with:

```bash
python tools/ci_v116_smoke.py
python tools/ci_salcapa_smoke.py
python tools/ci_salcapa_v21_smoke.py
python tools/ci_salcapa_v22_smoke.py
python tools/ci_salcapa_v23_smoke.py
python tools/ci_salcapa_v24_smoke.py
python tools/ci_salcapa_v25_smoke.py
python tools/ci_salcapa_v26_smoke.py
python tools/ci_salcapa_v27_smoke.py
python tools/ci_salcapa_v28_smoke.py
python tools/ci_salcapa_v29_smoke.py
python tools/ci_salcapa_operating_model_acceptance.py
```

Production is prepared for Microsoft Azure. No Azure deployment is automatic; billable infrastructure and production activation require explicit approval.
