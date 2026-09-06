# SalCAPA v3.25 release notes

## Passwordless runtime startup repair

SalCAPA v3.25 prevents optional legacy secret lookups from blocking the approved
passwordless Azure runtime. PostgreSQL Entra authentication no longer requests a
DSN secret, Azure Blob managed-identity configuration no longer requests a
connection-string secret, and managed-identity OIDC no longer requests a client
secret.

A focused regression smoke enforces these paths. The governed application
deployment remains immutable-digest based, Entra-only for PostgreSQL, restricted
to the approved development resource group, bounded by the existing cost
controls, and unchanged with respect to DNS and public production cutover.
