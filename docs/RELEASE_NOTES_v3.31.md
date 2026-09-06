# SalCAPA v3.31 release notes

## Governed recovery-readiness verification

SalCAPA v3.31 adds a passwordless, read-only Azure recovery-readiness verifier
for the approved development environment. The governed activation validates the
existing deployment against the frozen v3.30 runtime and fails closed unless:

- PostgreSQL 16 is ready, Entra-only, private, and exposes a valid restore point
  inside its 14-day backup window;
- evidence storage remains private and OAuth-only, with blob versioning and
  14-day blob and container soft-delete retention;
- Azure Monitor retains 30 days of telemetry within the 0.1 GB/day cap;
- the USD 25 monthly budget guardrail and its actual/forecast alerts remain
  configured; and
- the active Container App uses the exact approved immutable digest, HTTPS,
  no application secrets, and the complete live-readiness contract.

The verification emits only bounded, non-secret configuration evidence. It does
not restore data or mutate Azure resources, and it introduces no password,
client secret, DNS change, or production cutover.
