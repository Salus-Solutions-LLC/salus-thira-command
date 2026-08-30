# Build status

Current frozen application release: **Salus THIRA Command v1.9** at `release/v1.9` commit `d1ac9a0f711706e7d26b5df07aa408ede510afb9`. v1.10 Operational Assessment Workspace is under controlled validation on `development/v1.10`.

Authoritative references:

- Frozen application release: `release/v1.9` at `d1ac9a0f711706e7d26b5df07aa408ede510afb9`.
- Current governed development baseline: `main`.
- The active main-branch ruleset requires `validate`, `postgres-runtime`, `analyze`, and `container-runtime`.
- The active release ruleset makes every `release/*` branch immutable after creation.
- Product integration contract: `docs/SITE_INTEGRATION_v1.10.md`.

Prior frozen recovery branches remain unchanged through `release/v1.9`.

Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime/Member data and evidence are excluded from GitHub and recovered through the application backup/DR process.
