# Salus THIRA Command — GitHub Operating Model

This repository is the authoritative source-control record for Salus THIRA Command. GitHub preserves source history and release recovery; it is **not** a storage location for client records, evidence, operational intelligence, credentials, secrets, runtime databases, or backups.

## Branch roles

### `main`

`main` is always the latest fully validated stable release commit. It must never intentionally lag behind the newest frozen release.

### `development/vX.Y`

Active version development. New application work begins from the current `main` / latest frozen release. Development pushes receive CI, including source reconstruction, SQLite lifecycle testing, PostgreSQL lifecycle testing, dependency audit, and static security scanning.

### `validation/vX.Y-release`

Temporary validation-only branch. It should contain the exact release candidate plus, when needed, a harmless validation marker to trigger pull-request workflows. It is never the release source of truth and is closed without merge after validation.

### `release/vX.Y`

Immutable recovery pointer to the exact candidate commit that passed all release gates. Do not rewrite, amend, force-push, or add documentation after freeze. A correction becomes a new version.

### `governance/*`

Repository-control changes such as CI, security policy, CODEOWNERS, templates, and dependency automation. These changes are reviewed/tested like application changes before merging to `main`.

## Standard development/release flow

1. Start `development/vX.Y` from current `main`.
2. Make the smallest coherent application and governance changes.
3. Keep runtime/client data excluded through `.gitignore` and release-package scans.
4. Rebuild the version-specific deterministic source archive/delta.
5. Verify all target source SHA-256 values locally.
6. Push the development candidate and require green CI.
7. Open a draft `validation/vX.Y-release` PR targeting `main` for an independent CI and CodeQL cycle.
8. Require, as applicable:
   - exact-source reconstruction/verification;
   - Python compilation;
   - JavaScript syntax validation;
   - SQLite release lifecycle regression;
   - PostgreSQL 16 lifecycle and transaction regression;
   - dependency audit;
   - Bandit/static security gate;
   - fail-closed CodeQL findings gate;
   - clean release-package scan and recorded SHA-256.
9. Create `release/vX.Y` at the **exact tested development commit**, never at the validation-marker commit.
10. Close the validation PR **without merge**.
11. Fast-forward `main` to the exact frozen release commit.
12. Verify the prior release branch is unchanged.

## Reliability controls

- Workflows pin third-party Actions to immutable commit SHAs.
- Dependabot proposes controlled updates for Actions and Python dependencies.
- CI uses concurrency cancellation to avoid wasting runners on superseded commits.
- CI jobs have timeouts so hung external services cannot consume runners indefinitely.
- `main` is the stable baseline, reducing huge/stale validation diffs.
- Release branches have an Actions immutability alarm; any post-creation update is a policy violation requiring investigation.
- Version-specific source archives/deltas retain target SHA-256 values and fail closed on mismatch.

## Security controls

- Checkout credentials are not persisted into the workspace.
- Workflow permissions are read-only unless a workflow has a documented reason for more access.
- CODEOWNERS records accountable review ownership for security, CI, deployment, migration, archive, and core runtime files.
- Security findings must not be posted with sensitive data in ordinary GitHub issues.
- Client data, evidence, backups, runtime databases, `.env`, secrets, and sensitive logs never belong in Git.
- Static-analysis exceptions must be narrow and documented; blanket scanner suppression is prohibited.

## Efficiency controls

- Push CI runs on `main`, `development/**`, `governance/**`, and `release/**`; temporary validation branches rely on PR CI rather than generating redundant push runs.
- Development push CI plus independent PR CI provides two acceptance cycles without a third duplicate validation-branch push cycle.
- Dependabot groups routine dependency updates to reduce PR noise.
- CodeQL runs on `main`, PRs targeting `main`, weekly schedule, and manual dispatch.

## Platform limitation

The current private-repository GitHub plan/integration does not expose repository Rulesets for this repository. Repository-controlled safeguards therefore supplement, but do not replace, server-enforced branch protection. If the GitHub plan later supports Rulesets/required checks, enable them for `main` and `release/**` using the controls described below.

Recommended future Rulesets:

- `main`: require PR, require successful CI and CodeQL, block force pushes/deletion.
- `release/**`: block updates, force pushes, and deletion after creation.
- require signed commits/tags if Salus adopts an organizational signing policy.

## Recovery principle

A release is recoverable only when all three are preserved:

1. Git commit/release branch;
2. deterministic source archive/delta plus target hashes;
3. distributable/package checksum.

Runtime assessment data and evidence are recovered through the application backup/DR process, not from GitHub.
