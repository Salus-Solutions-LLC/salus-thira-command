# GitHub operating model

## Purpose and source boundaries

GitHub is the authoritative source-control and engineering-assurance home for Salus THIRA Command code. SharePoint/Microsoft 365 remains authoritative for controlled policies, SOPs, agreements, completed forms, business records, and project administration. Approved operational systems remain authoritative for client data, person records, protective intelligence, investigations, evidence, logs, and runtime backups.

Never move a record into GitHub merely to simplify automation. Store only source code, tests using fictional or irreversibly sanitized data, configuration examples without secrets, build instructions, and non-confidential engineering evidence.

## Standard change path

1. Start from current `main` and create one short-lived branch: `feature/`, `fix/`, `security/`, `chore/`, or `validation/`.
2. Keep the branch limited to one reviewable outcome. Do not use temporary upload branches as long-term storage.
3. Open a pull request to `main`; complete the confidentiality gate, risk classification, verification evidence, and rollback plan.
4. Require successful CI and CodeQL. Require owner review for security, identity, database, deployment, dependency, and GitHub-workflow changes.
5. Prefer squash merge so one reviewed PR produces one attributable `main` commit. Delete the merged topic branch.
6. Create a signed release tag after acceptance. Preserve release tags; retain release branches only while they have an active support or recovery purpose.

## Reliability controls

- Pin application and CI-tool dependencies; let Dependabot propose grouped, reviewable updates.
- Pin GitHub Actions to full commit SHAs and retain the human-readable release tag in a comment.
- Use concurrency cancellation so superseded runs do not consume capacity or produce ambiguous results.
- Set job timeouts and least-privilege workflow permissions.
- Keep SQLite and PostgreSQL runtime smoke tests, source-integrity verification, dependency audit, Bandit, CodeQL, and repository-hygiene checks mandatory by practice.
- Record rollback steps before merge. A release is not complete until restore and recovery prerequisites are known.

## Safety controls

- Never commit `.env` files, secrets, keys, certificates, databases, logs, backups, exports, controlled office documents, or client/person records.
- Treat pull-request text, workflow logs, artifacts, issue comments, and commit messages as repository content; the same confidentiality boundary applies.
- Use fictional test data. Do not sanitize by merely changing a name while leaving linkable facts.
- Keep workflow token permissions read-only unless a documented job requires more.
- Review dependency and Action updates before merge even when automated checks pass.

## Branch and recovery hygiene

Review branches monthly. Delete merged `feature/`, `fix/`, `security/`, `chore/`, `validation/`, and `tmp/` branches after confirming the commit is reachable from `main` or a retained release tag. Never force-update an accepted release tag. Export an encrypted repository mirror to an approved Salus backup location on a documented schedule; do not place runtime or client data in that mirror.

GitHub plan limitations currently prevent enforceable private-repository rulesets/branch protection. Until the plan supports them, the PR, owner-review, CI, and no-direct-push requirements are mandatory operating practice rather than platform-enforced controls.
