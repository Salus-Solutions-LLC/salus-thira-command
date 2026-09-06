# SalCAPA v3.21 release notes

## Import-safe Azure database bootstrap

- Starts the governed bootstrap utility through Python's module entry point so the application root remains importable inside the production container.
- Adds a smoke assertion for the exact Container Apps Job command and rejects the path-based invocation that caused `ModuleNotFoundError`.
- Advances immutable image publication and database-bootstrap source selection to this exact frozen release.
- Retains bounded redacted failure logs, exact Entra object-ID authority, passwordless authentication, and convergent cleanup.

This release does not deploy the SalCAPA application, change DNS, create long-lived credentials, or perform public cutover.
