# Salus THIRA Command v1.4.1 Release Notes

## Security and diagnostic handling

v1.4.1 preserves the v1.4 evidence-lifecycle and risk-governance behavior while closing the remaining full-branch CodeQL findings.

- External readiness, OIDC, backup, restore, and storage failures return generic messages with opaque correlation references.
- Internal security telemetry records the exception class, component, and correlation ID without retaining exception text that may contain secrets, paths, tokens, SQL, or client context.
- Local storage retains strict component validation and resolved-root/symlink containment.
- Dynamic SQL identifiers remain constrained through compile-time mappings and reviewed allowlists; data values remain bound parameters.

## GitHub reliability controls

- Development branches receive full-branch CodeQL analysis before pull-request review.
- CI prevents README, Docker, Windows, macOS/Linux, CI, and CodeQL reconstruction entrypoints from drifting to older source.
- Redundant validation-branch push CI is removed; the validation PR remains the independent acceptance cycle.
- A cancelled required check is recovered through a fresh commit/check suite; cancelled contexts are never bypassed.

## Release acceptance

The release gate requires exact deterministic reconstruction, SHA-256 verification, entrypoint consistency, Python/JavaScript compilation, SQLite and PostgreSQL 16 lifecycle smokes, security regression smoke, PostgreSQL transaction smoke, dependency audit, Bandit, and zero CodeQL findings.
