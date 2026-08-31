# Build status

Current frozen application release: **Salus THIRA Command v1.11** at `release/v1.11` commit `3bd72b4ec0c1061b8851db9fd2b528c7a8675372`. v1.12 Operational Capability Target Workspace is under governed validation on `development/v1.12`.

Authoritative references:

- Current frozen application release: `release/v1.11`.
- Current governed development branch: `development/v1.12`.
- The active main-branch ruleset requires validation, PostgreSQL, CodeQL, and container-runtime checks.
- The active release ruleset makes every `release/*` branch immutable after creation.

Frozen releases through v1.11 remain unchanged. Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime Member Client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
