## Purpose

Describe the change and the Salus THIRA Command requirement it satisfies.

## Safety and data handling

- [ ] No client data, evidence, credentials, secrets, `.env`, database, backup, or sensitive log artifacts are included.
- [ ] Test data is fictional or sanitized.
- [ ] Tenant/assessment boundaries and authorization behavior were considered.

## Source integrity

- [ ] The source reconstruction/verification chain succeeds from a clean checkout.
- [ ] New/changed archive parts and manifests are hash-verified.
- [ ] Frozen `release/vX.Y` branches were not rewritten.

## Validation

- [ ] Python compilation passes.
- [ ] JavaScript syntax validation passes.
- [ ] SQLite lifecycle/regression tests pass.
- [ ] PostgreSQL lifecycle/transaction tests pass when persistence behavior is affected.
- [ ] Dependency audit passes.
- [ ] Bandit/static security gate passes or any exception is narrowly documented.
- [ ] CodeQL findings gate passes for release candidates/security-sensitive changes.

## Governance

- [ ] Application version and risk-methodology version are changed only when appropriate.
- [ ] Audit/version/backup/export/migration effects were considered for governed entities.
- [ ] Release notes/runbooks are updated when operational behavior changes.

## Release handling

For a release candidate, identify the exact candidate commit and package SHA-256. Validation-only PRs must be closed **without merge** after the release branch is frozen; `main` is then fast-forwarded to the validated release commit.
