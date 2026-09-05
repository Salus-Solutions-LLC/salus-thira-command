# SalCAPA Azure cost and activation proposal

Pricing checked on 2026-09-04. All amounts are estimated Microsoft retail pay-as-you-go prices in USD for South Central US. Taxes, negotiated discounts, support plans, unusually high transactions, malware scanning, DNS registration, and usage above stated allowances are excluded. Azure prices can change; refresh this estimate immediately before any provisioning action.

Official references:

- Container Apps pricing: https://azure.microsoft.com/en-us/pricing/details/container-apps/
- PostgreSQL Flexible Server pricing: https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/
- Container Registry pricing: https://azure.microsoft.com/en-us/pricing/details/container-registry/
- Blob Storage pricing: https://azure.microsoft.com/en-us/pricing/details/storage/blobs/
- Azure Monitor pricing: https://azure.microsoft.com/en-us/pricing/details/monitor/
- Key Vault pricing: https://azure.microsoft.com/en-us/pricing/details/key-vault/
- Bandwidth pricing: https://azure.microsoft.com/en-us/pricing/details/bandwidth/
- Retail Prices API: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices

## Option A — approved lean SalCAPA production starting point

This is the active approved course of action for initial SalCAPA production use. It is intentionally capacity-constrained and is not highly available. Governance, identity, tenancy, evidence lifecycle, provenance, audit, backup/recovery, and operational handoff controls are not reduced to achieve the lower cost.

| Resource | Exact proposed configuration | Monthly planning estimate |
|---|---|---:|
| Resource group | One dedicated South Central US group | $0.00 |
| Azure Container Apps | Consumption environment, one SalCAPA app, scale 0–1 initially | $0–low single digits at low use |
| PostgreSQL Flexible Server | Burstable B1ms, PostgreSQL 16, one zone | about $12–13 |
| PostgreSQL storage | Minimum sensible supported storage, governed backup retention | low single digits |
| Container Registry | Basic | about $5 |
| Blob Storage | StorageV2 Hot, Standard_LRS initially, versioning and soft delete | low single digits |
| Key Vault | Standard, RBAC, purge protection | negligible at low transaction volume |
| Application Insights / Azure Monitor | Strictly bounded low-volume telemetry | expected within free/low-use allowance |
| Internet egress | Low-use pilot traffic | expected within free/low-use allowance |
| Target operating range |  | **approximately $15–25/month** |
| Proposed monthly authorization ceiling |  | **$30.00** |

### Approved cost controls

- Written approval record: **MD-APPROVAL-AZURE-LEAN-20260904**.
- Marc Duncan approved this course of action on 2026-09-04.
- $30 USD/month is a hard recurring Azure authorization ceiling for this starting architecture.
- Provisioning must stop if the current Azure estimate exceeds $30/month.
- The governed Azure Consumption budget is fixed at **$25.00/month**, below the $30 authorization ceiling.
- Notifications are required at **80% actual**, **100% forecasted**, and **100% actual** spend.
- The protected GitHub variable **AZURE_BUDGET_CONTACT_EMAIL** supplies the notification recipient at deployment time; no address is hard-coded in source.
- Budget alerts/checkpoints must be configured below the ceiling before production cutover.
- Capacity, redundancy, storage, telemetry, or other recurring-cost increases require a separate cost review and approval.
- No DNS change or public production cutover is authorized by this cost approval alone.

Pilot recovery target: PostgreSQL point-in-time recovery within the configured retention period; evidence protection through blob versioning, soft delete, controlled backup procedures, and operator-directed restore. The lean architecture does not promise automatic regional failover.

## Option B — previous controlled low-use App Service proposal

This earlier proposal remains documented for comparison but is **not the selected course of action**.

| Resource | Exact proposed configuration | Monthly estimate |
|---|---|---:|
| App Service | Linux B1, one instance | $13.14 |
| PostgreSQL Flexible Server | Burstable B1ms, PostgreSQL 16, one zone | $12.41 |
| PostgreSQL storage | 32 GiB Premium SSD, 14-day backup retention | $3.68 |
| Container Registry | Basic | $5.08 |
| Blob Storage | StorageV2 Hot, GRS, 25 GB allowance | $1.00 |
| Key Vault | Standard | $0.03 |
| Application Insights and Log Analytics | up to low-use allowance | $0.00 planning assumption |
| Internet egress | up to low-use allowance | $0.00 planning assumption |
| Previous ceiling |  | **$43.00** |

## Option C — previous production-ready high-availability proposal

This earlier proposal remains documented for future scale-up analysis but is **not authorized**.

| Resource | Exact proposed configuration | Monthly estimate |
|---|---|---:|
| App Service | Linux Premium v3 P0v3, two instances | $124.10 |
| PostgreSQL Flexible Server | General Purpose D2ds v5, zone-redundant HA | $259.88 |
| PostgreSQL storage | 128 GiB Premium SSD | $14.72 |
| PostgreSQL backup allowance | 35-day retention with geo-redundant backup allowance | $12.16 |
| Container Registry | Standard | $20.28 |
| Blob Storage | StorageV2 Hot, GRS, 250 GB allowance | $16.20 |
| Key Vault | Standard | $0.30 |
| Application Insights and Log Analytics | 10 GB/month planning allowance | $15.00 |
| Internet egress | 200 GB/month planning allowance | $8.70 |
| Previous ceiling |  | **$550.00** |

## Live identity and scope acceptance

Before foundation provisioning, `.github/workflows/azure-connection-verify.yml` must pass using passwordless GitHub OIDC. It verifies the exact approved subscription, Entra tenant, South Central US development resource group, and deployment-principal role assignments without creating or changing Azure resources. The deployment principal may not retain visible assignments outside the governed resource-group scope. It must have resource deployment authority and the scoped role-assignment authority required to grant the template's managed-identity roles.

The protected repository variable `AZURE_BUDGET_CONTACT_EMAIL` must contain the approved operational notification recipient before the foundation or application workflow can run.

## Activation boundary

The $30/month approval authorizes preparation and governed provisioning of the selected lean architecture only. Provisioning still requires the existing least-privilege Azure subscription and Entra context, workload identity, approved administrators/reviewers, resource-group scope, backup settings, and controlled GitHub deployment workflow.

No frozen branch may be rewritten. No validation pull request may be merged. No DNS change or public production cutover may occur without a separate explicit authorization.

The approval record identifier **MD-APPROVAL-AZURE-LEAN-20260904** must be preserved in the GitHub environment, deployment record, and SalCAPA audit history.