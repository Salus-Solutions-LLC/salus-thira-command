# Salus THIRA Command v0.9 Release Notes

## Theme
Accepted-risk accountability and governance.

## Added
- Dedicated Accepted Risk Register.
- Automatic register creation from authorized `Accept Risk` executive decisions.
- Required decision authority, residual exposure, and review date for risk acceptance.
- Risk owner, reconsideration trigger, review status, and closure/supersession basis.
- Command Center counts for active accepted risks and overdue reviews.
- Accepted-risk traceability through improvement → decision → accepted risk.
- Accepted-risk inclusion in executive reports, assessment exports, backups, migration, and revision history.

## Governance behavior
- Accepted-risk records cannot be deleted through the application.
- Active/under-review accepted risks require a review date.
- Closing an accepted risk requires a documented closure basis.
- Decision authority and source decision linkage are immutable after creation.

## Runtime foundation
All v0.8 database, identity, evidence, backup, telemetry, rate-limit, PostgreSQL, and security controls remain in place.
