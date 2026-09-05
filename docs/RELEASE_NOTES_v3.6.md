# SalCAPA v3.6 — Immutable approved Azure foundation activation

## Outcome

SalCAPA can activate the already approved lean Azure development foundation from an immutable governed record on `development/salcapa-platform` while preserving `main` unchanged. The activation is one-time, idempotent, passwordless, cost-bounded, and protected by the `salcapa-dev-approval` environment.

## Controls

- The activation record must reference the exact immutable head of `release/v3.6`.
- The source commit must be an ancestor of the activation commit.
- Operation, environment, region, suffix, approval record, $30 ceiling, and $25 operational budget are exact and fail closed.
- Unknown activation fields are rejected.
- GitHub authenticates through OIDC; no Azure client secret or publish profile is used.
- Deployment authority is rechecked at `rg-salcapa-dev` and may not exist outside that scope.
- Azure what-if reruns immediately before provisioning and rejects destructive deletes or Container App creation before runtime federation.
- The deployment name is deterministic for the frozen source commit.
- Successful provisioning must emit and validate the managed-identity federation contract.
- The Container App count must remain zero until the Entra runtime application and federated credential exist.

## Reconstruction

The SalCAPA application source is unchanged from the deterministic v3.3 archive. This release retains that verified reconstruction path and adds governed Azure activation controls.

## Delivery state

This candidate defines and validates the activation mechanism. No activation record has been committed, and no Azure resource, credential, DNS record, or deployment has been created by this release candidate.
