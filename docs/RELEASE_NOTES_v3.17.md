# SalCAPA v3.17 release notes

## Exact bootstrap-stage verification

- Normalizes Azure-managed identity object IDs to canonical UUID form before use.
- Fails explicitly if the deployment does not emit the governed identity output.
- Records non-secret stage completion for transient resource deployment, PostgreSQL administrator creation, exact administrator-contract verification, and Container Apps Job start.
- Emits a bounded, non-secret administrator diagnostic when Azure returns a principal that differs from the activation contract.
- Retains immutable source and image checks, passwordless authentication, convergent cleanup, and server-controlled Marc Duncan role and clearance mapping.

No production application, DNS change, client secret, database password, or public cutover is created by this release.
