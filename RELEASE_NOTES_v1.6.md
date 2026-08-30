# Salus THIRA Command v1.6 — Professional Risk Override Review Governance

- Active overrides receive a future review date; legacy API clients receive a controlled 90-day default.
- Overdue overrides stop supplying assigned risk while calculated risk remains unchanged.
- One reassessment trigger is created per overdue episode.
- Controlled review requires a documented outcome and future date, records reviewer/time, restores Current status, and resolves the trigger.
- Withdrawal resolves any open lifecycle trigger.
- Lifecycle transitions are audited and versioned.
- SQLite, PostgreSQL 16, container, dependency, Bandit, and CodeQL gates retain the complete prior regression chain.
