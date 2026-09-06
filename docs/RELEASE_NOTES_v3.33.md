# SalCAPA v3.33 release notes

## Governed Microsoft Entra identity acceptance evidence

SalCAPA v3.33 makes each successful Microsoft Entra authorization-code sign-in
a persisted, tenant-scoped acceptance event. The server records the mapped user,
role, clearance, authentication method, provider, acceptance time, session
expiry, and privacy-preserving SHA-256 digests of the validated subject, issuer,
and source network. Browser claims cannot set tenant, role, clearance, authority
source, lifecycle state, or acceptance outcome.

Only a tenant's System Administrator can read that tenant's acceptance history.
Protected Members cannot access the administrative ledger, and failed, replayed,
disabled, unknown, wrong-tenant, wrong-issuer, and wrong-audience attempts cannot
create acceptance records. Existing security telemetry continues to record those
fail-closed outcomes.

Portable tenant backup and governed restore now include identity acceptance
history and validate its tenant, user, authority-source, authentication-method,
and subject-digest integrity before restoration. The OIDC smoke gate proves
server-mapped authority, persistence, privacy protection, rejection behavior,
and cross-tenant administrative isolation without using a password or client
secret.

The runtime change is covered by a deterministic v3.32-to-v3.33 source delta.
No Azure resource, credential, DNS record, or production environment is changed
by this release.
