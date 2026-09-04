# SalCAPA v2.2 — governed operational engagements and tasking

- Extends authorized SalOPS requests into persisted operational engagements.
- Preserves request authority and tenant provenance server-side when an engagement is created.
- Adds controlled Planning → Mobilizing → Active → Demobilizing → Closed lifecycle gates.
- Adds accountable operational task assignment, start, completion, cancellation, and result records.
- Separates controlled internal field-report details from explicitly released Protected Member summaries.
- Withholds operational instructions, communications plans, locations, personnel details, and draft reports from Protected Member access.
- Requires every task to be resolved and at least one field report released before engagement closure.
- Completes the originating request and creates one governed SalOPS-to-SalTHIRA reassessment handoff on closure.
- Includes engagements, tasks, field reports, audit history, and PostgreSQL identities in portable backup and recovery controls.
- Preserves deterministic reconstruction and SQLite/PostgreSQL parity.
