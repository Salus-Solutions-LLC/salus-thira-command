# Build status

Current supported application release: **Salus THIRA Command v1.5** at `release/v1.5` commit `1d8f296f9a0e8163c878e7821a79cf8a4d407850`. v1.6 Professional Risk Override Review Governance is under validation on `development/v1.6` and is not frozen yet.

Authoritative references:

- Frozen application release: `release/v1.4.1` at `8917886a6972b5f9f3dad16515ce52813aaa653f`.
- Current governed development baseline: `main`.
- `main` includes the validated production-container runtime gate merged in PR #24.
- The active main-branch ruleset requires `validate`, `postgres-runtime`, `analyze`, and `container-runtime`.
- The active release ruleset makes every `release/*` branch immutable after creation.

Recent frozen recovery branches:

- `release/v1.2`
- `release/v1.3`
- `release/v1.4`
- `release/v1.4.1`

Deterministic source reconstruction and integrity verification are documented under `tools/README_source_integrity.md`. Runtime/client data and evidence are excluded from GitHub and recovered through the application backup/DR process.
