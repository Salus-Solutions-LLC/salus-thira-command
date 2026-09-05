# SalCAPA v3.10 — Observable Azure readiness evidence

## Outcome

The live Azure acceptance workflow now emits sanitized provider-registration states and the current development resource inventory to both the private workflow log and job summary. Hourly governance runs can therefore distinguish an unresolved subscription prerequisite from a cleared condition without retrying deployment.

## Controls

- Provider state checks remain read-only and cover every namespace required by the approved lean foundation.
- Resource inventory is restricted to `rg-salcapa-dev`.
- Logs contain only provider names, registration states, Azure resource types, and resource names; no credentials or secret values are emitted.
- The workflow continues to validate passwordless OIDC, the exact tenant/subscription/resource group, constrained RBAC, and a non-provisioning what-if.
- No provider registration, resource deployment, DNS change, or public cutover occurs in this evidence path.
