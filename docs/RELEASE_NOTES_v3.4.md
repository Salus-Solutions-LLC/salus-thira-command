# SalCAPA v3.4 — Governed Azure foundation sequencing

## Outcome

SalCAPA can provision the approved lean Azure development foundation before a runtime Entra application client ID exists. The foundation emits the exact managed-identity federation contract required for the subsequent passwordless runtime binding, removing the prior circular dependency without introducing a client secret.

## Controls

- Foundation remains restricted to the governed development branch and protected GitHub environment.
- The approved authorization record and fixed $30 monthly ceiling remain mandatory.
- Every provisioned resource records the exact source commit.
- The foundation emits and verifies the federation issuer, managed-identity subject, audience, redirect URI, and managed-identity client ID.
- Application deployment rejects a missing or malformed runtime application UUID.
- The globally unique Azure resource suffix is constrained to 4–6 lowercase alphanumeric characters so both development and production storage-account names remain within Azure’s 24-character limit.
- Federated credential values must be taken from the deployment outputs and may not be guessed.
- No DNS change or public production cutover is authorized.

## Reconstruction

The application source is unchanged from the deterministic v3.3 archive. v3.4 retains and verifies that exact reconstruction path while adding governed infrastructure sequencing.

## Delivery state

This candidate prepares the controlled foundation deployment. It does not itself provision Azure resources, create credentials, change DNS, or deploy SalCAPA.
