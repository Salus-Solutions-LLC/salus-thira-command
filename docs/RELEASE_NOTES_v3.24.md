# SalCAPA v3.24 release notes

## Bounded live deployment verification

- Bounds every live readiness and sign-in request with explicit connection and total timeouts.
- Replaces an unbounded runtime verification wait with a deterministic maximum retry window.
- Captures only a bounded tail of Azure Container App console logs when readiness fails.
- Redacts password, secret, token, and connection-string-shaped values before diagnostic output.
- Keeps deployment fail-closed until the health contract and exact Salus Entra authorization redirect are verified.
- Keeps the recurring foundation preflight valid after deployment while rejecting any attempted Container App creation, modification, or deletion.
- Retains immutable-image, passwordless identity, private PostgreSQL 16, HTTPS-only ingress, zero-to-one replica, budget, and no-custom-DNS controls.

## Governance

This candidate preserves all frozen releases, `main`, and `development/v1.17`. It introduces no credentials, DNS changes, or public production cutover.
