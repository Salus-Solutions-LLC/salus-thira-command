# Salus THIRA Command v1.7 — Assessment Reassessment Lifecycle Governance

- Assessment workflow status and reassessment currency remain separate.
- Past reassessment dates automatically produce Reassessment Overdue state.
- One High-severity reassessment trigger is created per overdue episode.
- Generic edits cannot forge reassessment dates or lifecycle state.
- Controlled review requires a documented outcome and future date, records reviewer/time, restores Current status, and resolves the trigger.
- SQLite, PostgreSQL 16, container, dependency, Bandit, and CodeQL gates retain the complete prior regression chain.
