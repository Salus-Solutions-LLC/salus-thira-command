# SalCAPA v2.1

SalCAPA is Salus Solutions' secure intelligence, risk, and operations platform.

## Product structure

- **SalCAPA** provides the role-aware Common Operating Picture for Protected Members and authorized Salus personnel.
- **SalINTEL** collects, qualifies, validates, analyzes, and monitors intelligence.
- **SalTHIRA** identifies threats and hazards, establishes context and capability targets, assesses capabilities, identifies gaps, and supports risk and impact decisions.
- **SalOPS** governs approved requests, authorization, assignment, operations, results, and feedback.

Shared platform controls provide tenant isolation, identity and authorization, evidence lifecycle governance, reassessment triggers, professional judgment, executive decisions, accepted risk, immutable reporting, audit/version history, backup, and governed recovery.

## Development and release controls

GitHub is authoritative. Development occurs on governed development branches. Every release candidate must pass deterministic reconstruction, SQLite, PostgreSQL 16, production-container, dependency audit, Bandit, repository hygiene, and CodeQL gates. Validation pull requests are closed without merge. Frozen release branches are immutable.

Reconstruct and verify this candidate with:

```bash
python tools/reconstruct_v21_source.py
python tools/verify_v21_source.py
```

Run the complete SalCAPA governed-workflow smoke with:

```bash
python tools/ci_v116_smoke.py
python tools/ci_salcapa_smoke.py
python tools/ci_salcapa_v21_smoke.py
```

Production is prepared for Microsoft Azure. No Azure deployment is automatic; billable infrastructure and production activation require explicit approval.
