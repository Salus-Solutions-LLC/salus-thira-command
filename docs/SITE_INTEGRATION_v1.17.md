# Site integration — v1.17

The approved Salus THIRA Command product interface may expose these operations only when connected to the authoritative persisted API:

- `POST /api/reports/{assessment_id}` creates an immutable governed report version.
- `GET /api/reports/{assessment_id}` lists report provenance and authority state.
- `POST /api/reports/versions/{report_id}/transition` advances one controlled authority gate.
- `GET /api/reports/versions/{report_id}/snapshot` verifies and returns the exact persisted snapshot.
- `GET /api/audit/assessments/{assessment_id}` returns tenant-isolated audit and version history.
- Backup verification and DR validation remain non-destructive.
- Restore requests require a passed DR validation, exact scope, documented reason, and recorded authorization.
- Restore execution remains hidden unless the maintenance-window control enables it.

Do not display build numbers, branches, CI status, or release gates in the primary product interface. Do not publish these controls to a duplicate Site.
