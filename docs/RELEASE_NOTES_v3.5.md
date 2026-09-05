# SalCAPA v3.5 — Live Azure foundation preflight

## Outcome

SalCAPA now performs a real Azure Resource Manager what-if against the exact governed development target before any protected foundation deployment. The preflight authenticates through GitHub workload identity federation and creates no Azure resources.

## Verified boundaries

- Target subscription, SALUS tenant, `rg-salcapa-dev`, and region must match the governed repository variables.
- The GitHub deployment principal must retain only the approved resource-group assignments.
- Foundation suffix is fixed to the validated six-character value `b48224`.
- Proposed changes must remain inside `rg-salcapa-dev`.
- Destructive deletes fail validation.
- Container App creation before runtime Entra federation fails validation.
- Approval record, $30 authorization ceiling, $25 operational budget, PostgreSQL administrator identity, and deployment principal are supplied to the what-if.
- The preflight never calls `az deployment group create`.

## Reconstruction

The application source remains unchanged from the deterministic v3.3 archive. This candidate retains the verified reconstruction path and extends Azure production-readiness acceptance.

## Delivery state

The live preflight passed without provisioning. Protected foundation deployment, Entra runtime federation, immutable application deployment, DNS, and public cutover remain separately governed.
