# SalCAPA v3.23 release notes

## Governed viewable development deployment

- Adds a protected, activation-record-driven path for deploying the exact frozen SalCAPA image to Azure Container Apps.
- Requires an immutable Azure Container Registry SHA-256 digest and verifies that the digest exists before deployment.
- Authenticates GitHub to Azure only through workload identity federation.
- Rechecks the exact Azure subscription, tenant, `rg-salcapa-dev` scope, private PostgreSQL 16 configuration, and disabled registry administrator.
- Runs Azure what-if before creating or updating the application.
- Keeps the approved cost boundary at zero-to-one Consumption replicas with the $30 monthly ceiling and $25 operational budget.
- Verifies the live image, user-assigned managed identity, HTTPS-only ingress, absence of application secrets, readiness endpoint, and Microsoft Entra sign-in redirect.
- Uses the Azure-generated development address; no custom DNS or public production cutover is performed.

## Governance

This candidate preserves all frozen releases, `main`, and `development/v1.17`. The controlled activation can deploy only from the exact governed record on `development/salcapa-platform` after the protected `salcapa-dev-approval` gate passes.
