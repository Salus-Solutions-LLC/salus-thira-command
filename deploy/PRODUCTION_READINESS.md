# Salus THIRA Command v0.7 Production Readiness Gate

v0.7 deliberately fails production readiness when SQLite is still the active runtime database unless an explicit controlled exception is authorized. The managed PostgreSQL target can be validated before cutover with `python tools/postgres_preflight.py`.

Recommended production baseline:

- OIDC authentication through Microsoft Entra ID or another approved OIDC provider.
- Azure Key Vault with managed identity (`SALUS_SECRET_BACKEND=azure_keyvault`).
- Azure Blob Storage using `SALUS_AZURE_STORAGE_ACCOUNT_URL` and managed identity.
- ClamAV or an approved malware-scanning service with `SALUS_REQUIRE_AV=1`.
- Redis-backed distributed rate limiting for multiple application replicas.
- Azure Monitor / Application Insights or an approved SIEM destination for centralized telemetry.
- Managed PostgreSQL target validated before data migration/cutover.
- Backup packages validated through both integrity verification and DR validation before being counted as recoverable.
- GitHub CI and CodeQL required before production merge/deployment.

The SQLite-to-PostgreSQL exporter produces deterministic NDJSON plus SHA-256 hashes. It is a migration staging artifact, not an automatic production cutover.
