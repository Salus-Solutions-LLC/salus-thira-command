## Purpose

Describe the operational outcome and the smallest change that achieves it.

## Change classification

- [ ] Application code
- [ ] Security or identity control
- [ ] Database/schema/migration
- [ ] Deployment/infrastructure
- [ ] Documentation-only
- [ ] Dependency or GitHub workflow

## Verification

- [ ] Source archive reconstruction/integrity passes when applicable
- [ ] Python compilation and JavaScript syntax checks pass
- [ ] SQLite smoke test passes
- [ ] PostgreSQL smoke test passes when database behavior changes
- [ ] Dependency audit, Bandit, repository-hygiene scan, and CodeQL pass
- [ ] Rollback procedure is documented below

## Data and confidentiality gate

- [ ] No client data, person records, case files, evidence, logs, backups, databases, credentials, tokens, secrets, controlled DOCX/PDF files, or production exports are included
- [ ] Test data is fictional or irreversibly sanitized
- [ ] New configuration values use environment-variable placeholders only

## Risk and rollback

Risk level: Low / Moderate / High

Rollback command or procedure:

## Review evidence

Link the successful workflow run and identify any accepted exception. Do not paste secrets, client information, or controlled-document content into this PR.
