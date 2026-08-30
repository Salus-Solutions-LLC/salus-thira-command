# Salus THIRA Command v1.8 — Executive Decision Review Lifecycle Governance

v1.8 makes executive-decision review dates enforceable governance controls while preserving the immutability of the original decision.

- Decision disposition and review lifecycle currency remain separate.
- Past review dates automatically produce Review Overdue state and one High-severity reassessment trigger per overdue episode.
- Repeated authoritative reads and sweeps do not create duplicate triggers.
- New dated decisions require a future review date; ordinary edits cannot rewrite immutable decisions or forge lifecycle state.
- A controlled review requires a future date and documented outcome, records reviewer/time, restores Current state, and resolves the trigger.
- Automatic transitions and controlled reviews are audited and versioned.
- Authoritative lists, dashboards, reports, exports, and backups sweep lifecycle state before output or write transactions.
- SQLite and PostgreSQL 16 execute the same lifecycle behavior.

The complete v1.4.1 through v1.7 lifecycle and security regression chain remains gated.
