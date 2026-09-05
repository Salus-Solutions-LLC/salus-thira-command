# SalCAPA v3.10 — Machine-readable Azure provider readiness

## Outcome

The live Azure acceptance workflow now exposes a machine-readable, non-disclosing provider-readiness step. Scheduled governance can determine whether the subscription prerequisite has cleared without retrying deployment, publishing resource metadata to logs, or generating a failed-workflow notification.

## Controls

- The readiness step checks every namespace required by the approved lean foundation.
- It emits no provider states, resource names, identifiers, credentials, or secrets.
- A missing provider marks only the readiness step unsuccessful through `continue-on-error`; the overall read-only connection verification remains available.
- Foundation provisioning remains separately fail-closed and cannot begin until every provider is registered.
- OIDC, tenant, subscription, resource-group, constrained RBAC, what-if, cost, and no-premature-Container-App controls remain unchanged.

## Delivery state

This candidate performs read-only Azure checks. It does not register providers, provision resources, create credentials, change DNS, or perform public cutover.
