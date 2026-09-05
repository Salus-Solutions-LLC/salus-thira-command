# SalCAPA v3.20 release notes

## Bounded database-bootstrap failure evidence

- Captures up to 300 lines from the exact failed Container Apps Job execution before transient cleanup removes it.
- Selects the governed `bootstrap` container and exact execution identifier.
- Redacts common password, secret, token, and connection-string assignments before logs reach GitHub Actions.
- Keeps log capture failure-tolerant so cleanup always remains authoritative.
- Adds Azure-policy source assertions for bounded, container-specific, redacted diagnostics.

This release does not retry the database bootstrap, deploy the application, change DNS, or create credentials.
