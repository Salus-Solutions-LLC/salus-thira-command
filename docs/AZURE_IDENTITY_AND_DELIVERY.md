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

## Staged Entra activation

Foundation and federation must be completed in this order to avoid a circular dependency:

1. Run the protected `foundation` operation on `development/salcapa-platform` using the approved development resource group, region, 4–6 character lowercase alphanumeric globally unique suffix, and approval record. The 4–6 character boundary keeps every generated development and production storage-account name within Azure’s 24-character limit. Foundation provisioning does not require `ENTRA_RUNTIME_CLIENT_ID` and does not create the Container App.
2. Capture the governed deployment outputs: managed-identity client ID, federation issuer, federation subject, federation audience, and exact runtime redirect URI. The workflow verifies these outputs and records the non-secret federation contract in its job summary.
3. An authorized Entra administrator creates or identifies the single-tenant SalCAPA runtime application registration, registers only the emitted HTTPS callback, and adds one federated identity credential using the emitted values.
4. Record the application client ID as the non-secret GitHub repository variable `ENTRA_RUNTIME_CLIENT_ID`. The `deploy` operation rejects a missing or malformed UUID.
5. Pre-provision each permitted person in SalCAPA with their immutable Entra object ID, approved SalCAPA tenant, role, clearance, and active status.
6. Run governed application deployment and login acceptance for a Protected Member and Salus user, unknown and disabled subjects, cross-tenant denial, state replay, issuer/audience rejection, and server-derived role behavior.

The federated credential must use issuer `https://login.microsoftonline.com/<tenant-id>/v2.0`, the case-sensitive managed identity principal (object) ID as its subject, and `api://AzureADTokenExchange` as its audience. These values are emitted by the exact foundation deployment and must not be guessed.

The Bicep deployment records the exact source commit on every provisioned resource. Foundation outputs are configuration evidence, not authority to create a different application, credential, resource set, or role assignment. Creating the approved app registration or federated credential does not create a long-lived credential. DNS and public production cutover remain separately governed.

## Release and rollback

Every candidate must pass deterministic reconstruction, SQLite, PostgreSQL 16, production-container, dependency audit, Bandit, repository hygiene, CodeQL, Azure infrastructure policy, and live passwordless Azure scope checks. Azure naming policy constrains the shared suffix before provisioning so the generated resource names are valid in both development and production. A validation pull request is closed without merge.

Application rollback selects a prior approved image digest from the same registry. Database recovery restores to a separate PostgreSQL server for independent validation. Identity configuration changes require a governed record and must preserve fail-closed tenant and subject mapping.
