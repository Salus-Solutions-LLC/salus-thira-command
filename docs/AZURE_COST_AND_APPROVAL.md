# SalCAPA Azure cost and activation proposal

Pricing checked on 2026-09-03. All amounts are estimated Microsoft retail pay-as-you-go prices in USD for South Central US, calculated with 730 runtime hours and 30.4 days per month. Taxes, negotiated discounts, support plans, unusually high transactions, malware scanning, DNS registration, and usage above the stated allowances are excluded. Azure prices can change; refresh this estimate in the Azure calculator immediately before approval and provisioning.

Official references:

- App Service pricing: https://azure.microsoft.com/en-us/pricing/details/app-service/linux/
- PostgreSQL Flexible Server pricing: https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server/
- Container Registry pricing: https://azure.microsoft.com/en-us/pricing/details/container-registry/
- Blob Storage pricing: https://azure.microsoft.com/en-us/pricing/details/storage/blobs/
- Azure Monitor pricing: https://azure.microsoft.com/en-us/pricing/details/monitor/
- Key Vault pricing: https://azure.microsoft.com/en-us/pricing/details/key-vault/
- Bandwidth pricing: https://azure.microsoft.com/en-us/pricing/details/bandwidth/
- Retail Prices API: https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices

## Option A — controlled low-use pilot

This option is suitable for acceptance, migration, and limited named-user production use. It is not highly available.

| Resource | Exact proposed configuration | Monthly estimate |
|---|---|---:|
| Resource group | One dedicated South Central US group | $0.00 |
| App Service | Linux B1, one instance | $13.14 |
| PostgreSQL Flexible Server | Burstable B1ms, PostgreSQL 16, one zone | $12.41 |
| PostgreSQL storage | 32 GiB Premium SSD, 14-day backup retention | $3.68 |
| Container Registry | Basic, up to 10 GB included | $5.08 |
| Blob Storage | StorageV2 Hot, GRS, 25 GB allowance, versioning and soft delete | $1.00 |
| Key Vault | Standard, RBAC, purge protection; 10,000-operation allowance | $0.03 |
| Application Insights and Log Analytics | Analytics logs; up to the first 5 GB/month allowance | $0.00 |
| Internet egress | Up to the first 100 GB/month | $0.00 |
| Estimated subtotal |  | **$35.34** |
| 20% operating contingency |  | **$7.07** |
| Proposed monthly authorization ceiling |  | **$43.00** |

Pilot recovery target: database point-in-time recovery within the configured retention period; evidence protection through GRS, blob versioning, and soft delete. Recovery is operator-directed and does not promise automatic failover.

## Option B — production-ready starting point

This option is the recommended approval target after nonproduction acceptance. It provides redundant application capacity and zone-redundant database compute.

| Resource | Exact proposed configuration | Monthly estimate |
|---|---|---:|
| Resource group | One dedicated South Central US group | $0.00 |
| App Service | Linux Premium v3 P0v3, two instances | $124.10 |
| PostgreSQL Flexible Server | General Purpose D2ds v5, zone-redundant HA (primary plus standby) | $259.88 |
| PostgreSQL storage | 128 GiB Premium SSD | $14.72 |
| PostgreSQL backup allowance | 35-day retention with geo-redundant backup allowance | $12.16 |
| Container Registry | Standard, up to 100 GB included | $20.28 |
| Blob Storage | StorageV2 Hot, GRS, 250 GB plus transaction/replication allowance | $16.20 |
| Key Vault | Standard, RBAC, purge protection; 100,000-operation allowance | $0.30 |
| Application Insights and Log Analytics | 10 GB/month ingestion allowance; first 5 GB assumed free | $15.00 |
| Internet egress | 200 GB/month allowance; first 100 GB assumed free | $8.70 |
| Estimated subtotal |  | **$471.34** |
| 15% operating contingency |  | **$70.70** |
| Proposed monthly authorization ceiling |  | **$550.00** |

The production ceiling is an approval control, not permission to provision. Alerts should be set at 50%, 75%, 90%, and 100% of the approved monthly ceiling. Provisioning must stop if the current Azure calculator estimate exceeds the approved ceiling.

## Approval boundary

No Azure resource, workload identity, credential, DNS record, or production deployment may be created from this proposal alone. Activation requires a written Marc Duncan approval record naming:

1. selected option and monthly ceiling;
2. Azure subscription and Entra tenant;
3. region and production domain;
4. named Entra administrators and GitHub production-environment reviewers;
5. recovery objectives and backup retention;
6. authorization to create nonproduction resources first.

The approval record identifier must be preserved in the GitHub environment, deployment record, and SalCAPA audit history.
