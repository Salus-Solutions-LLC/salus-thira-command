# Build status

Current frozen application release: **Salus THIRA Command v1.12** at `release/v1.12` commit `2562b3b686fe3c10b7745f9d8753b0bbcef54539`. v1.13 Operational Evidence Lifecycle Workspace is under governed validation on `development/v1.13`.

Authoritative references:

- Current frozen application release: `release/v1.12`.
- Current governed development branch: `development/v1.13`.
- The active main-branch ruleset requires validation, PostgreSQL, CodeQL, and container-runtime checks.
- The active release ruleset makes every `release/*` branch immutable after creation.

Frozen releases through v1.12 remain unchanged. Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime Member Client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
