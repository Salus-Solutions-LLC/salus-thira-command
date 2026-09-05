# SalCAPA Azure identity and delivery design

## Authority boundary

Microsoft Entra ID authenticates people. SalCAPA authorizes them from pre-provisioned server-side mappings of the immutable Entra object ID to a SalCAPA user, tenant, role, clearance, and lifecycle status. Token role/group claims, request bodies, and browser headers never select tenant, role, clearance, lifecycle, provenance, audit, handoff, or Protected Member authority.

Production automatic user provisioning is disabled. Unknown or disabled subjects fail closed. The tenant-specific issuer and token `tid` claim must match the configured SALUS Entra tenant, and ID tokens are validated for issuer, audience, nonce, and signature before a session is created.

## Passwordless runtime sign-in

The SalCAPA Container App uses a user-assigned managed identity. The Microsoft Entra application registration has a federated identity credential that trusts only that managed identity. During the authorization-code exchange, SalCAPA requests an `api://AzureADTokenExchange/.default` managed-identity token and submits it as a standards-based client assertion. No OIDC client secret is configured or stored.

Server-controlled Container App settings are:

- `SALUS_AUTH_MODE=oidc`
- `SALUS_OIDC_TENANT_ID` — the approved SALUS tenant ID
- `SALUS_OIDC_DISCOVERY_URL` — the tenant-specific Microsoft identity-platform discovery document
- `SALUS_OIDC_CLIENT_ID` — the non-secret runtime application client ID
- `SALUS_OIDC_CLIENT_AUTH_METHOD=managed_identity`
- `SALUS_OIDC_MANAGED_IDENTITY_CLIENT_ID` — the Container App user-assigned identity client ID
- `SALUS_OIDC_REDIRECT_URI` — the exact HTTPS Container App callback
- `SALUS_OIDC_PROVIDER_NAME=entra`
- `SALUS_OIDC_AUTO_PROVISION=0`

The readiness endpoint validates the complete configuration and obtains the managed-identity assertion fail closed without exposing assertion or exception detail.

## Runtime managed identity

The user-assigned managed identity receives only:

- `AcrPull` on the governed registry;
- `Storage Blob Data Contributor` on the evidence container;
- `Key Vault Secrets User` on the SalCAPA vault;
- the separately provisioned least-privilege PostgreSQL database role.

It receives no subscription Owner, unrestricted Contributor, storage account key, database password, or Key Vault Administrator role.

## GitHub deployment identity

GitHub Actions authenticates to Azure through workload identity federation. No Azure client secret, publish profile, storage key, database password, or OIDC client secret is stored in GitHub.

The deployment service principal is scoped to `rg-salcapa-dev` with Contributor and a constrained Role Based Access Control Administrator assignment. The condition permits only `AcrPush`, `AcrPull`, `Storage Blob Data Contributor`, and `Key Vault Secrets User` assignments to service principals.

Protected GitHub environments remain the approval boundary. Production federation accepts only the corresponding protected environment subject. Images are deployed by immutable digest from the governed registry.

## Entra activation prerequisites

Before application deployment, an authorized Entra administrator must:

1. create or identify the single-tenant SalCAPA runtime application registration;
2. register only the exact HTTPS callback emitted by the Bicep template;
3. add a federated identity credential whose issuer and subject identify the SalCAPA user-assigned managed identity;
4. record the application client ID as the non-secret GitHub variable `ENTRA_RUNTIME_CLIENT_ID`;
5. pre-provision each permitted person in SalCAPA with their immutable Entra object ID, approved tenant, role, clearance, and active status;
6. run login acceptance for a Protected Member and Salus user, unknown and disabled subjects, cross-tenant denial, state replay, issuer/audience rejection, and server-derived role behavior.

The federated credential must use issuer `https://login.microsoftonline.com/<tenant-id>/v2.0`, the case-sensitive managed identity principal (object) ID as its subject, and `api://AzureADTokenExchange` as its audience. These three values must match the managed-identity assertion exactly.

Creating the app registration or federated credential does not create a long-lived credential. Azure resources, DNS, and public production cutover remain separately governed.

## Release and rollback

Every candidate must pass deterministic reconstruction, SQLite, PostgreSQL 16, production-container, dependency audit, Bandit, repository hygiene, CodeQL, and Azure infrastructure policy checks. A validation pull request is closed without merge.

Application rollback selects a prior approved image digest from the same registry. Database recovery restores to a separate PostgreSQL server for independent validation. Identity configuration changes require a governed record and must preserve fail-closed tenant and subject mapping.
