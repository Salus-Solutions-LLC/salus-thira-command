# SalCAPA Azure backup and restore runbook

## Recovery objectives proposed for approval

- Production database recovery point objective: 15 minutes or the best supported PostgreSQL Flexible Server point-in-time interval, whichever is greater.
- Production service recovery time objective: 4 hours for a validated regional service restoration.
- Pilot database recovery point objective: 24 hours.
- Pilot service recovery time objective: 1 business day.
- PostgreSQL retention: 14 days for pilot, 35 days with geo-redundant backup for production.
- Evidence: Blob Storage GRS, versioning, 30-day blob and container soft delete in production.

These are proposed objectives until Marc Duncan approves them.

## Daily automated evidence

Record, without protected content:

- PostgreSQL backup and health state;
- newest restorable time;
- storage redundancy, versioning, and soft-delete configuration;
- application container digest;
- tenant backup manifest inventory and integrity status;
- failed backup or telemetry events.

Alerts do not authorize a restore.

## Monthly non-destructive validation

1. Select a signed backup/restore exercise record naming tenant scope, operator, reviewer, reason, and expected hashes.
2. Create a portable backup and verify its manifest before use.
3. Restore PostgreSQL point-in-time data into an isolated temporary server or approved test database.
4. Restore evidence objects into an isolated prefix or temporary account.
5. run schema, row-count, object-hash, tenant-isolation, lifecycle, audit, and governed-handoff checks;
6. verify that no notification, operational handoff, or external integration can execute from the restored environment;
7. record achieved recovery point and elapsed recovery time;
8. destroy temporary resources after evidence is approved.

Validation must never overwrite production.

## Real restore authorization

A real restore requires:

- incident/change record;
- exact tenant and time scope;
- named authorizing executive;
- named restore operator and independent reviewer;
- verified backup manifest and object hashes;
- documented customer and legal/retention impact;
- approved target server and storage location;
- rollback and communication plan.

Set `SALUS_ALLOW_RESTORE=1` only inside the bounded restore operation. Return it to `0` before the restored service is admitted to traffic.

## Database restoration

1. Freeze application writes and record the final database and container state.
2. Preserve the affected server; do not overwrite or delete it.
3. Restore PostgreSQL Flexible Server to a new server at the authorized point in time.
4. Apply the least-privilege Entra database mappings.
5. Run migrations only if the restored schema requires the exact validated application digest.
6. Run readiness, tenant isolation, audit continuity, and lifecycle tests.
7. Compare authoritative counts and hashes with the signed restoration record.
8. Obtain independent reviewer acceptance before traffic cutover.

## Evidence restoration

1. Recover the exact approved blob versions into an isolated location.
2. Verify stored object hashes against authoritative evidence records.
3. Preserve legal holds and retention dates.
4. Deny serving any object with a failed or missing hash.
5. Promote recovered objects only through a controlled, audited action.

## Return to service

- confirm Entra authentication fails closed;
- confirm Protected Member and Salus roles remain tenant-aware;
- confirm evidence, audit history, report versions, and handoff idempotency;
- confirm telemetry contains no secrets or protected evidence content;
- record the active application digest, database server, restore point, and storage account;
- keep the prior environment isolated until formal closure.


## Governed live development readiness verification

The activation at `deploy/azure/activations/recovery-readiness-dev.json` runs a
protected, passwordless, read-only verification against the existing development
resources. It confirms the PostgreSQL restore window and 14-day retention,
evidence versioning and soft-delete controls, Azure Monitor retention and daily
cap, budget notifications, exact application digest, and live dependency
readiness. It creates no server, restores no data, mutates no resource, and does
not authorize a real recovery.

A clean-room restore exercise remains separately governed and must target an
isolated temporary server or database. Readiness verification is evidence that
the recovery prerequisites are present; it is not evidence that a restore has
completed.
