# SalCAPA v3.32 release notes

## Deterministic clean-room recovery and rollback

SalCAPA v3.32 adds an end-to-end recovery rehearsal that runs against ephemeral
SQLite and PostgreSQL 16 databases and temporary evidence storage. The exercise:

- creates and verifies a portable tenant backup;
- requires a passed recovery validation and an independent restore authorizer;
- changes the isolated tenant and restores the verified snapshot;
- proves an unrelated tenant remains unchanged;
- validates the automatic pre-restore safety backup;
- rolls back to the exact pre-restore tenant state; and
- returns restore admission to fail-closed after the exercise.

The rehearsal discovered and repairs a backup filename collision that could occur
when a requested backup and its automatic safety backup were created within the
same second. Backup filenames now contain a server-generated microsecond
timestamp and random nonce, and the regression gate proves the selected package
and safety package remain distinct.

The runtime change is covered by a deterministic v3.25-to-v3.32 source delta.
The exercise uses no live member data, creates no Azure resources, and performs
no DNS change or production cutover.
