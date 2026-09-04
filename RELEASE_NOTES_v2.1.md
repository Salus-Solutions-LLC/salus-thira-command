# SalCAPA v2.1 — governed reporting, audit, and recovery

- Adds immutable Executive report snapshots generated from authoritative assessment data.
- Binds every report to an assessment version and SHA-256 provenance record.
- Enforces Draft → Reviewed → Approved → Released authority gates with role-specific separation.
- Adds tenant-isolated assessment audit and version history with Protected Member redaction.
- Adds governed restore requests requiring a passed recovery validation, documented scope and reason, independent authorization, a maintenance window, and a pre-restore safety backup.
- Prevents client payloads from forging report, restore, tenant, provenance, audit, or handoff state.
- Restricts SalINTEL and SalOPS internal lifecycle actions and operational detail to authorized Salus personnel while retaining the role-aware Protected Member Common Operating Picture.
- Preserves the unified SalCAPA visual system and removes engineering/build terminology from the product interface.
- Preserves deterministic reconstruction and SQLite/PostgreSQL parity.
