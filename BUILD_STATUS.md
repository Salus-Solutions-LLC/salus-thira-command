# Build status

Current frozen application release: **Salus THIRA Command v1.13** at `release/v1.13` commit `4cd972038cccb68aa73313b08e5607679b68a75e`. v1.14 Operational Gap and Improvement Workspace is under governed validation on `development/v1.14`.

Authoritative references:

- Current frozen application release: `release/v1.13`.
- Current governed development branch: `development/v1.14`.
- The active main-branch ruleset requires validation, PostgreSQL, CodeQL, and container-runtime checks.
- The active release ruleset makes every `release/*` branch immutable after creation.

Frozen releases through v1.13 remain unchanged. Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime Member Client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
