# Build status

Current frozen application release: **Salus THIRA Command v1.16** at `release/v1.16` commit `7b2459bca59a505cc9e0a99327a5794627ba40b0`. v1.17 Reports, Audit, and Recovery Operations Workspace is under governed validation on `development/v1.17`.

Authoritative references:

- Current frozen application release: `release/v1.16`.
- Current governed development branch: `development/v1.17`.
- The active main-branch ruleset requires validation, PostgreSQL, CodeQL, and container-runtime checks.
- The active release ruleset makes every `release/*` branch immutable after creation.

Frozen releases through v1.16 remain unchanged. Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime Member Client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
