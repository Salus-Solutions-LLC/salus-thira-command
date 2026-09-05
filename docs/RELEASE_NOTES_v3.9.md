# SalCAPA v3.9 — Azure provider readiness and partial-state inventory

## Outcome

Foundation activation now fails before deployment when the Azure subscription has not registered every required resource provider. Live connection acceptance also records the current resource-group inventory and provider states without creating or changing resources.

## Controls

- Provider readiness is checked before what-if and deployment for Microsoft.App, Microsoft.ContainerRegistry, Microsoft.DBforPostgreSQL, Microsoft.Insights, Microsoft.KeyVault, Microsoft.ManagedIdentity, Microsoft.Network, Microsoft.OperationalInsights, Microsoft.Storage, and Microsoft.Consumption.
- Any provider not in the Registered state stops activation before a deployment command.
- Live acceptance inventories existing resources in rg-salcapa-dev and reports provider readiness in the private GitHub job summary.
- Provider checks do not auto-register namespaces and do not broaden the resource-group-scoped deployment identity.
- Existing frozen-source, protected approval, OIDC, cost, deletion, and no-premature-Container-App controls remain in force.

## Failure containment

The v3.8 activation reached Azure and failed because several subscription resource providers were unregistered. This release adds deterministic preflight coverage and an inventory path for detecting any partial state before retry.

## Delivery state

This candidate is read-only with respect to live Azure state. It does not register providers, provision resources, create credentials, change DNS, or perform public cutover.
