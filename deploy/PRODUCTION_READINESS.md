# Salus THIRA Command v1.4 Production Readiness Gate

The preferred production baseline is PostgreSQL plus managed identity/secrets and managed evidence storage.

## Required production baseline

- PostgreSQL is the healthy runtime database.
- Approved OIDC/Entra authentication and server-derived authorization.
- Managed secret provider such as Azure Key Vault.
- Managed evidence object storage.
- Approved malware scanning with fail-closed uploads.
- Redis-backed distributed rate limiting for multiple replicas.
- Centralized security telemetry/SIEM.
- TLS, private networking/firewall restrictions, and approved ingress/WAF controls.
- Portable tenant backups with successful integrity and DR validation.
- CI, dependency audit, Bandit, and CodeQL required before deployment.
- Approved records-retention/legal-hold schedule.
- Penetration testing and formal security/privacy review.

## v1.4 evidence-governance verification

Before production approval, verify that:

- validity date and verification status are separate;
- expiry automatically marks evidence Stale while preserving verification as a separate dimension;
- stale evidence cannot earn improvement-validation or professional-override evidence credit;
- expiry creates one accountable reassessment trigger;
- controlled lifecycle review is required to restore Current status;
- reports, exports, backups, and risk calculations refresh lifecycle before use; and
- audit/version history preserves stale and review actions.
