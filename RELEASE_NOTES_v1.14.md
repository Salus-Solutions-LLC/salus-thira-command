# Salus THIRA Command v1.14 — Operational Gap and Improvement Workspace

v1.14 activates governed capability-gap and improvement-action workflows linked to the operational assessment workspace.

## Product capability

- Gap records are tenant-isolated and may reference only capabilities in the same assessment.
- Gap type, severity, description, root cause, owner, and lifecycle state use bounded governed fields.
- Improvement actions may reference only gaps in the same assessment and retain cost, schedule, feasibility, consequence reduction, mission benefit, sustainability, compliance, staffing, expected capability gain, dependencies, and owner.
- Priority scores are calculated by the server from the recorded factors and cannot be supplied or overwritten by clients.
- New gaps start Open; new improvements start Proposed with Pending validation.
- Gap and improvement lifecycle changes require controlled transition actions with documented reasons.
- Completing an improvement creates exactly one open Capability Validation reassessment trigger.
- Controlled validation requires Verified evidence whose lifecycle is Current and records evidence, outcome, effectiveness, validator, and timestamp.
- Generic edits cannot forge lifecycle, validation, priority, tenant, timestamp, audit, or version state.
- Every governed creation, edit, transition, validation, and trigger change writes audit and immutable version history atomically.

## Release safety

The frozen v1.13 source is reconstructed and hash-verified before the deterministic v1.14 delta is applied. SQLite, PostgreSQL 16, container runtime, dependency audit, Bandit, CodeQL, release entrypoint, and repository-boundary gates remain mandatory. `main` and prior frozen release branches remain unchanged.
