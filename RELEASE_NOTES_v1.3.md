# Salus THIRA Command v1.3 Release Notes

## Professional risk override governance

v1.3 introduces an append-only Professional Risk Override Register. Calculated risk is never overwritten by professional judgment.

Each override preserves the calculated current-risk state, assigned professional-risk state, reason, authority, optional same-assessment Verified evidence, review date, creator, timestamp, supersession history, and governed withdrawal history.

## Key safeguards

- decision authority is required to record or withdraw an override;
- assigned score is constrained to 0–100 and the assigned band is derived consistently;
- supporting evidence, if cited, must belong to the same assessment and be Verified;
- cross-assessment threat/evidence links fail closed;
- a new override supersedes rather than edits the prior active record;
- direct generic update/delete of overrides is prohibited;
- current, predicted residual, and validated residual calculations remain unchanged by an override;
- override history is included in traceability, reports, exports, backups, audit, and version snapshots.

## Methodology version

Application version: **1.3.0**  
Risk methodology version: **1.1.0**

The application advances because governance behavior changed. The scoring methodology does not advance because the numerical risk formula did not change.
