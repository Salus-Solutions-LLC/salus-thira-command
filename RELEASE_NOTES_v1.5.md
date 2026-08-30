# Salus THIRA Command v1.5 — Accepted Risk Review Governance

v1.5 turns accepted-risk review dates into enforced lifecycle controls.

- Active and Under Review risks automatically become `Review Overdue` after the review date.
- Each overdue episode creates one High-severity reassessment trigger without duplication.
- Review workflow status remains separate from review lifecycle currency.
- Generic edits cannot renew the review date or forge review lifecycle fields.
- A controlled review requires a documented outcome and future review date, records reviewer/time, restores Current status, and resolves the overdue trigger.
- Overdue and review actions write audit and entity-version history.
- Dashboard, accepted-risk lists, executive reports, exports, and backups refresh lifecycle state before authoritative output.
- SQLite and PostgreSQL use the same application path and release smoke.

The v1.4.1 evidence lifecycle and diagnostic-disclosure security controls remain regression-gated.
