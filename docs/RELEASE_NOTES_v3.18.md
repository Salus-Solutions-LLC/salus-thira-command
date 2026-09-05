# SalCAPA v3.18 release notes

## Current frozen-source promotion contract

- Advances governed immutable image publication from frozen SalCAPA v3.15 to the exact frozen v3.17 source.
- Advances the database-bootstrap source contract to the same frozen v3.17 release while retaining immutable commit and registry-digest verification.
- Keeps publication and bootstrap bound to explicit development activation records and the protected approval environment.
- Retains passwordless GitHub workload identity, scoped Azure authority, PostgreSQL password authentication disabled, transient administrator cleanup, and server-controlled initial-user mapping.
- Updates Azure policy validation so drift back to the superseded frozen source fails closed.

This release changes no DNS, creates no client secret or database password, and performs no public or production cutover.
