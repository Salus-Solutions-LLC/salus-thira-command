# Salus THIRA Command v1.17

## Reports, Audit, and Recovery Operations

- Creates immutable Executive report snapshots from authoritative assessment data.
- Preserves the exact assessment version and SHA-256 provenance for every report.
- Enforces Draft → Reviewed → Approved → Released authority transitions.
- Provides tenant-isolated assessment audit and entity-version history.
- Adds controlled restore requests requiring a passed, non-destructive recovery validation.
- Requires explicit restore scope, reason, authorization, maintenance-window enablement, and a pre-restore safety backup.
- Records report and recovery actions in audit and security telemetry.
- Maintains identical SQLite and PostgreSQL 16 behavior.

The controlled validation pull request is closed without merge after all release gates pass. Prior frozen releases and `main` remain unchanged.
