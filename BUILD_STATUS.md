# Build status

Current frozen application release: **Salus THIRA Command v1.8** at `release/v1.8` commit `507671914c26b1593317467394e28cefe275ad86`. v1.9 Governed Product Intake and Site Integration is under validation on `development/v1.9`.

Authoritative references:

- Frozen application release: `release/v1.8` at `507671914c26b1593317467394e28cefe275ad86`.
- Current governed development baseline: `main`.
- The active main-branch ruleset requires `validate`, `postgres-runtime`, `analyze`, and `container-runtime`.
- The active release ruleset makes every `release/*` branch immutable after creation.
- Product integration contract: `docs/SITE_INTEGRATION_v1.9.md`.

Prior frozen recovery branches remain unchanged through `release/v1.8`.

Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime/Member data and evidence are excluded from GitHub and recovered through the application backup/DR process.
