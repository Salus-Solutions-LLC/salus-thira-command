# SalCAPA v3.14 release notes

## Governed passwordless database bootstrap

- Adds a one-time Container Apps Job path inside the existing development virtual network for private PostgreSQL initialization.
- Uses a transient managed identity as an additional PostgreSQL Entra administrator, then removes that administrator, job, and identity after a successful or failed run.
- Creates the normal SalCAPA runtime identity as a non-administrator PostgreSQL principal with access limited to the `salcapa` database and application schema.
- Initializes the existing deterministic SalCAPA schema with demonstration seeding disabled.
- Pre-provisions users only from an exact activation record keyed by immutable Microsoft Entra object ID; tenant, role, clearance, and lifecycle state remain server controlled.
- Rejects unknown activation fields, duplicate identities, malformed object IDs, unapproved roles, mutable image references, wrong registry, and any password or client-secret path.

No Container App, DNS record, client secret, database password, or public production cutover is created by this release candidate.
