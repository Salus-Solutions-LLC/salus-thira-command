# Security Policy

Salus THIRA Command is a private Salus Solutions repository. Security issues must be handled as controlled records and must not expose client, operational, intelligence, credential, or evidence data.

## Reporting a security issue

Do **not** open a public or ordinary repository issue containing a vulnerability, credential, secret, client identifier, assessment data, evidence, operational information, or exploit detail.

Report suspected security issues privately to the Salus repository owner/administrator. Include only the minimum information needed to reproduce or assess the issue, and use sanitized test data.

If a credential, token, key, password, connection string, or other secret may have been exposed, treat it as compromised and rotate/revoke it immediately rather than relying on deletion from Git history.

## Repository handling rules

- Never commit `.env` files, database files, evidence attachments, backups, client exports, logs containing sensitive data, or production secrets.
- Use fictional/sanitized data in tests, screenshots, issues, and pull requests.
- Keep production credentials in the approved secret provider; do not place them in GitHub source files or workflow YAML.
- Security-control changes require the same CI, PostgreSQL, source-integrity, and CodeQL gates as application changes.
- Release branches are immutable recovery points. Corrections are made in a new development/release version, not by rewriting a frozen release.

## Supported security baseline

The latest commit on `main` is the supported stable source baseline. Frozen `release/vX.Y` branches are retained for reproducibility and recovery, but security corrections should be delivered in a new supported release unless an emergency response requires otherwise.
