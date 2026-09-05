# SalCAPA v3.3 release candidate

## Governed capability

- Passwordless Microsoft Entra authorization-code exchange using the Container App user-assigned managed identity as a federated client assertion.
- Tenant-specific issuer and token-tenant validation.
- Immutable Entra object-ID mapping to server-controlled SalCAPA tenant, role, clearance, and lifecycle state.
- Production automatic provisioning disabled; unknown and disabled subjects fail closed.
- Managed-identity federation included in production readiness without exposing tokens or internal failures.
- Azure Container App configuration and controlled deployment accept only non-secret runtime identity identifiers.

## Verification boundary

SQLite and PostgreSQL identity regression coverage exercises successful login, server-derived authority, unknown subjects, email-link rejection, disabled mappings, cross-tenant denial, state replay, invalid issuer, invalid audience, and absence of an OIDC client secret in token exchange.

No Azure resources, credentials, DNS records, or public production deployment are created by this candidate.
