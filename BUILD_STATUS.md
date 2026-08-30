# Build status

Current frozen application release: **Salus THIRA Command v1.7** at `release/v1.7` commit `72a76a6b4906bb94e61402bd56496682f2be1175`. v1.8 Executive Decision Review Lifecycle Governance is under validation on `development/v1.8`.

Authoritative references:

- Frozen application release: `release/v1.7` at `72a76a6b4906bb94e61402bd56496682f2be1175`.
- Current governed development baseline: `main`.
- `main` includes the validated production-container runtime gate merged in PR #24.
- The active main-branch ruleset requires `validate`, `postgres-runtime`, `analyze`, and `container-runtime`.
- The active release ruleset makes every `release/*` branch immutable after creation.

Recent frozen recovery branches:

- `release/v1.2`
- `release/v1.3`
- `release/v1.4`
- `release/v1.4.1`
- `release/v1.5`
- `release/v1.6`
- `release/v1.7`

Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime/client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
