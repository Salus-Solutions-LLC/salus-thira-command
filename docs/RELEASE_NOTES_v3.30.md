# SalCAPA v3.30 release notes

## Governed live-runtime acceptance

SalCAPA v3.30 makes Azure application acceptance fail closed against the complete
public readiness contract. A deployment is accepted only when the live
development runtime confirms:

- Microsoft Entra OIDC through managed identity;
- Entra-only PostgreSQL connectivity;
- Azure Key Vault identity availability;
- Azure Blob evidence-storage read/write/delete health;
- Azure Monitor telemetry initialization; and
- an enabled, healthy rate limiter.

The verifier rejects diagnostic fields and sensitive connection material in the
public payload. Azure deployment also compares the Container App's non-secret
runtime settings with the governed passwordless configuration before probing the
application. No password, client secret, DNS change, or production cutover is
introduced.
