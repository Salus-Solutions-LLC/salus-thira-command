# SalCAPA v3.34 release notes

## Governed live Azure point-in-time recovery

SalCAPA v3.34 adds and accepts a bounded, passwordless Azure PostgreSQL
point-in-time recovery exercise for the development environment. The exercise
requires the protected GitHub approval environment and an exact governed
activation record bound to the frozen v3.33 application source.

The operation restores a server-calculated point 15 minutes before execution
into the fixed isolated temporary server `salcapa-dev-b48224-pitr`. It fails
closed if the target already exists or the point is outside Azure's reported
restore window. Acceptance verifies PostgreSQL 16, Entra-only authentication,
disabled public database access, and presence of the `salcapa` database.

The exercise proves the live Container App remains attached to the unchanged
source database and never admits the restored server to traffic. A cleanup trap
deletes the temporary server after success or failure and fails the run if
cleanup cannot be verified.

The first live exercise exposed an Azure CLI option-compatibility defect after
the restore completed. Cleanup succeeded. The corrected operation then passed
end to end. No client secret, database password, DNS change, member-data
overwrite, application cutover, or production operation occurred.

Application source is unchanged from v3.33 and remains deterministically
reconstructable and verifiable through the v3.33 source archive.
