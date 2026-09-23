# SalCAPA 3.170 Release Notes

## Outcome

SalCAPA 3.170 corrects the production PostgreSQL identity-return path for automatic Microsoft 365 knowledge ingestion.

## Correction

- Uses an explicit cross-database `RETURNING id` clause when creating a knowledge candidate.
- Ensures newly inserted knowledge candidates return their generated IDs before immutable audit events are written.
- Adds regression checks requiring the explicit identity-return and fail-closed guard to remain in the ingestion path.

## Unchanged controls

- Every pending file remains eligible for automatic processing without a human ingestion exception queue.
- Originals are not deleted.
- Destination bytes must pass SHA-256 verification before the intake source is moved to `90 Processed Intake`.
- Citation metadata and processing provenance remain hash-bound to the exact source.
