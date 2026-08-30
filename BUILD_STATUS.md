# Build status

Current frozen application release: **Salus THIRA Command v1.10** at `release/v1.10` commit `8ca2c29f6725b0c31f3cf2d42a77ff96a73a5ae6`. v1.11 Operational Threat and Scenario Workspace is under controlled validation on `development/v1.11`.

Authoritative references:

- Frozen application release: `release/v1.10` at `8ca2c29f6725b0c31f3cf2d42a77ff96a73a5ae6`.
- Current governed development baseline: `main`.
- The active main-branch ruleset requires `validate`, `postgres-runtime`, `analyze`, and `container-runtime`.
- The active release ruleset makes every `release/*` branch immutable after creation.
- Product integration contract: `docs/SITE_INTEGRATION_v1.11.md`.

Prior frozen recovery branches remain unchanged through `release/v1.10`.

Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime/Member data and evidence are excluded from GitHub and recovered through the application backup/DR process.
