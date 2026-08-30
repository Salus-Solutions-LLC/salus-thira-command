# Security policy

## Reporting

Do not place vulnerability details, credentials, client information, person records, evidence, or production configuration in an ordinary issue or pull request.

Use a private GitHub security advisory when that feature is available. Otherwise, contact the repository owner through an established Salus business channel and provide only the minimum information needed to establish a secure response path.

## Repository boundary

This repository contains source code, tests, sanitized configuration examples, build instructions, and non-confidential engineering records only. It is not an approved repository for:

- client or person data;
- operational intelligence, case files, evidence, or reports;
- controlled policies, SOP masters, agreements, or completed forms;
- runtime databases, exports, backups, logs, or telemetry payloads;
- credentials, private keys, tokens, certificates, or production connection strings.

Those records remain in their approved Salus systems of record. A private repository is not, by itself, authorization to store controlled information.

## Supported code

Security fixes are applied to `main` and the current supported release branch. Older release branches are retained for traceability but do not receive routine fixes unless specifically authorized.

## Response expectations

The repository owner will acknowledge a verified report, establish severity and affected versions, preserve evidence, coordinate remediation, and publish only the minimum safe release information. Do not exploit, exfiltrate, or retain real data while demonstrating a vulnerability.
