# SalCAPA Azure identity and delivery design

## Trust boundaries

Microsoft Entra ID authenticates people. SalCAPA derives role and tenant access from server-side mappings of immutable Entra object IDs and approved group IDs. Request bodies and browser headers never select authority, lifecycle, provenance, tenant, audit, or handoff state.

GitHub Actions authenticates to Azure through workload identity federation. No Azure client secret, publish profile, storage key, or database password is stored in GitHub.

## Entra groups

Create these groups only after approval and record their immutable object IDs:

- SalCAPA Platform Administrators
- SalINTEL Analysts
- SalTHIRA Assessment Directors
- SalOPS Operations Leads
- Protected Member Executives
- Protected Member Contributors
- Protected Member Viewers

Protected Member group membership must also map to an approved SalCAPA tenant. A user with a valid account but no active tenant mapping is denied. Salus personnel cross-tenant access requires an explicit server-side authorization record and audit event.

## Runtime managed identity

The App Service system-assigned managed identity receives only:

- Storage Blob Data Contributor scoped to the evidence container;
- Key Vault Secrets User scoped to the SalCAPA vault;
- database login mapped to a least-privilege PostgreSQL application role.

It receives no subscription Owner, User Access Administrator, unrestricted Contributor, storage account key, or Key Vault Administrator role. Database schema migration uses a separate short-lived deployment identity and is not available to the running application.

## GitHub deployment identity

Use one federated identity per environment. Subject claims are restricted to the corresponding protected GitHub environment. Production federation accepts only the `salcapa-prod-approval` environment.

Production deployment requires:

- Marc Duncan or an explicitly delegated approver as a required reviewer;
- deployment only from `development/salcapa-platform` during validation;
- an immutable Azure Container Registry digest;
- a written approval/change record;
- green validation for the exact commit and digest;
- no self-approval by the initiating actor.

The deployment identity is scoped to the dedicated SalCAPA resource group. Assign only the resource-provider roles required to update App Service, the registry, monitoring, storage, Key Vault configuration, and PostgreSQL configuration. Role-assignment creation remains a separate administrator action.

## Delivery sequence

1. Reconstruct and verify the exact candidate.
2. Run SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, CodeQL, and Bicep gates.
3. Build the container once and record its SHA-256 digest.
4. Open a controlled validation PR and close it without merge after every gate is green.
5. Record Marc Duncan's approval and Azure cost ceiling.
6. Configure the protected GitHub environment and workload-identity federation.
7. Run infrastructure what-if.
8. Provision nonproduction resources and validate Entra, database, evidence, telemetry, backup, and restore behavior.
9. Authorize production separately.
10. Deploy the same validated digest and record the resulting Azure deployment ID.

## Rollback

Rollback never uses a mutable tag. The protected workflow selects a previously validated digest, runs readiness checks, and records the approval and deployment IDs. Database recovery restores into a separate server; production data is never overwritten in place.
