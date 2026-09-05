# SalCAPA v3.16 release notes

## Observable, convergent Azure bootstrap execution

- Preserves the validated passwordless v3.15 PostgreSQL administrator REST lifecycle.
- Surfaces structured Azure deployment errors instead of retaining them only in a runner-local file.
- Verifies the exact transient identity object ID emitted by the deployment before administrator creation.
- Waits for the transient Container Apps Job and managed identity deletions to converge before any subsequent attempt.
- Retains failure-safe cleanup, immutable activation, exact Entra user authority, and least-privilege runtime database access.

No Container App application deployment, DNS change, client secret, database password, or public production cutover is performed by this release.
