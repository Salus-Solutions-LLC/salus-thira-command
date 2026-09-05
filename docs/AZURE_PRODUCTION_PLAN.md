# SalCAPA Azure production plan

## Purpose

This plan removes the unavailable legacy ChatGPT Site from the SalCAPA critical path. GitHub remains authoritative. Azure becomes the controlled runtime only after explicit approval of the final resource list and recurring cost.

## Prepared architecture

- Azure Container Apps Consumption running the immutable SalCAPA container image by digest, initially scaled 0–1.
- Azure Container Registry with administrative and anonymous access disabled.
- Azure Database for PostgreSQL Flexible Server 16 as the authoritative relational store.
- Microsoft Entra ID for user authentication and PostgreSQL administrator authentication.
- Private PostgreSQL networking through a delegated subnet and private DNS.
- Azure Key Vault using RBAC, purge protection, and managed identity.
- Azure Blob Storage with public access and shared-key access disabled.
- Application Insights and Log Analytics with sanitized application telemetry.
- GitHub Actions validation without Azure credentials.
- Production deployment through GitHub workload identity federation after approval.

The infrastructure template now describes the approved lean deployment boundary without creating it. The governed starting architecture uses a burstable PostgreSQL 16 B1ms server with 14-day backup retention and Standard_LRS evidence storage. General-purpose compute, zone-redundant high availability, longer retention, or geo-redundant storage remain future scale options and require a separate cost review and approval. The exact tier and authorization ceiling remain governed by `AZURE_COST_AND_APPROVAL.md`.

## Control boundaries

- No workflow deploys automatically.
- Applying the template would create billable resources and therefore requires Marc Duncan's written approval record and the protected GitHub environment.
- No long-lived Azure client secret is stored in GitHub.
- Production images must use a SHA-256 digest from the target environment's governed registry; mutable tags and cross-registry substitution are prohibited.
- PostgreSQL password authentication and public network access are disabled.
- The approved PostgreSQL Entra administrator is supplied by immutable object ID at deployment time.
- The application managed identity receives only evidence-container Blob Data Contributor, Key Vault Secrets User, and registry pull roles.
- Application database privileges are provisioned separately using least privilege after the managed identity exists.
- `main` and `release/**` remain human-controlled and immutable under repository rulesets.
- Validation pull requests are closed without merge.

## Activation sequence

1. Retain the approved lean cost model, service tiers, authorization record, and approximately $30 monthly ceiling.
2. Confirm the Azure subscription, `southcentralus` region, SALUS Entra tenant, `rg-salcapa-dev`, and named PostgreSQL Entra administrator group.
3. Retain the protected GitHub environments, passwordless deployment federation, scoped RBAC, and documented non-secret repository variables.
4. Run credential-free Bicep and policy validation on the governed development branch.
5. Run the passwordless live Azure connection acceptance and verify the deployment principal has only the approved resource-group scope.
6. Run the live, non-provisioning foundation what-if with suffix `b48224`; reject any resource outside `rg-salcapa-dev`, destructive delete, or Container App creation before runtime federation.
7. Review the exact what-if result and then run the protected `foundation` operation. The fixed $25 monthly budget and notifications are created with the foundation before the other billable resources.
8. Capture the foundation outputs for the managed-identity client ID, federation issuer, immutable managed-identity subject, `api://AzureADTokenExchange` audience, and exact HTTPS redirect URI.
9. Create or identify the single-tenant SalCAPA runtime app registration, register only the emitted callback, add one federated identity credential using the emitted values, and record its non-secret client ID as `ENTRA_RUNTIME_CLIENT_ID`. Do not create a client secret.
10. Publish the approved image digest to the governed registry.
11. Grant the application managed identity its least-privilege PostgreSQL role and pre-provision approved Entra object-ID mappings in SalCAPA.
12. Deploy the Container App only after federation exists and the protected environment approves the immutable digest.
13. Run database migration, backup, restore, passwordless Entra login, fail-closed identity, tenant-isolation, monitoring, and budget-alert tests.
14. Complete the controlled validation PR and close it without merge.
15. Authorize production provisioning and DNS only after every release gate is green.

The live preflight is read-only: it invokes Azure Resource Manager what-if and never calls `az deployment group create`. It therefore creates no Azure resource, credential, DNS record, or deployment.
## Rollback

- Application rollback selects a prior approved container digest from the same governed registry.
- Database rollback uses a verified point-in-time restore into a separate server; production data is never overwritten in place.
- Blob recovery uses soft delete/versioning and a controlled restore record.
- DNS changes occur only after the replacement deployment passes readiness and authentication checks.
