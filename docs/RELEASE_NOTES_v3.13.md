# SalCAPA v3.13 — Governed Immutable Image Publication

## Outcome

This candidate adds the protected, passwordless mechanism for publishing the actual SalCAPA application container from an exact frozen release into the existing governed Azure Container Registry.

## Controls

- Publication is triggered only by an exact governed activation-record push on `development/salcapa-platform`.
- The protected `salcapa-dev-approval` environment gates authorization before any OIDC token is issued.
- The image source must be the exact head of frozen `release/v3.13`.
- Azure login uses the approved passwordless GitHub workload identity.
- The target subscription, tenant, resource group, region, registry, and AcrPush assignment are verified before publication.
- The container runs as UID 10001 and its archived source is verified before push.
- A full source-commit tag is used; `latest` is prohibited.
- The published artifact is selected and reported by immutable SHA-256 digest.
- The workflow creates no client secret, deploys no Container App, changes no DNS, and does not broaden Azure RBAC.

## Activation status

No image activation record is included in this release candidate. Publication can occur only after this exact candidate passes every required gate, its validation pull request is closed without merge, and `release/v3.13` is frozen at the all-green commit.
