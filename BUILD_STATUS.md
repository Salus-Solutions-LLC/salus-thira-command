# Build status

Current frozen application release: **Salus THIRA Command v1.15** at `release/v1.15` commit `0effaa938388c62355d9f652e102420d1d63fbcb`. v1.16 Executive Decisions and Accepted Risk Workspace is under governed validation on `development/v1.16`.

Authoritative references:

- Current frozen application release: `release/v1.15`.
- Current governed development branch: `development/v1.16`.
- The active main-branch ruleset requires validation, PostgreSQL, CodeQL, and container-runtime checks.
- The active release ruleset makes every `release/*` branch immutable after creation.

Frozen releases through v1.15 remain unchanged. Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime Member Client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
