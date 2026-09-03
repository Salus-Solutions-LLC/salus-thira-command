# SalCAPA Azure production plan

## Purpose

This plan removes the unavailable legacy ChatGPT Site from the SalCAPA critical path. GitHub remains authoritative. Azure becomes the controlled runtime only after explicit approval of the final resource list and recurring cost.

## Prepared architecture

- Linux Azure App Service running the immutable SalCAPA container image by digest.
- Azure Database for PostgreSQL Flexible Server as the authoritative relational store.
- Microsoft Entra ID for user authentication and PostgreSQL managed-identity authentication.
- Azure Key Vault using RBAC, purge protection, and managed identity.
- Azure Blob Storage with public access and shared-key access disabled.
- Application Insights and Log Analytics with sanitized application telemetry.
- GitHub Actions validation without Azure credentials.
- Production deployment through GitHub workload identity federation after approval.

The PostgreSQL server is intentionally excluded from the first infrastructure template until its sizing, availability mode, retention, recovery objectives, Entra administrator, and networking cost are approved. This prevents accidental creation of the most consequential recurring resource.

## Control boundaries

- No workflow deploys automatically.
- No long-lived Azure client secret is stored in GitHub.
- Production images must use a SHA-256 digest; mutable tags are prohibited.
- The application managed identity receives only Blob Data Contributor and Key Vault Secrets User roles.
- Database privileges will be provisioned separately using least privilege.
- `main` and `release/**` remain human-controlled and immutable under repository rulesets.
- Validation pull requests are closed without merge.

## Activation sequence

1. Approve the exact Azure cost model and service tiers.
2. Confirm the Azure subscription, region, Entra tenant, production domain, and named Entra administrators.
3. Validate Bicep and policy checks on the governed development branch.
4. Create a dedicated resource group and workload-identity federation.
5. Provision nonproduction resources first.
6. Run database migration, backup, restore, fail-closed authentication, and tenant-isolation tests.
7. Complete the controlled validation PR and close it without merge.
8. Authorize production provisioning and DNS only after every release gate is green.

## Rollback

- Application rollback selects the prior signed container digest.
- Database rollback uses a verified point-in-time restore into a separate server; production data is never overwritten in place.
- Blob recovery uses soft delete/versioning and a controlled restore record.
- DNS changes occur only after the replacement deployment passes readiness and authentication checks.

