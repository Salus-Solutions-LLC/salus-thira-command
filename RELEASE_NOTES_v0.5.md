# Salus THIRA Command v0.5

## Security and tenancy
- Server-enforced tenant isolation across assessments, records, evidence, reports, audit views, and backups.
- New session authentication mode with PBKDF2-SHA256 password hashing, HttpOnly cookies, server-side role enforcement, tenant identity, and sensitivity clearance.
- Assessment-level access assignments for session users.
- Standard, Restricted, Sensitive, and Highly Sensitive evidence controls.

## Recovery
- Tenant-specific backup packages with consistent SQLite snapshots and tenant-specific attachments.
- SHA-256 backup manifest and verification.
- Audited backup downloads.
- Restore disabled by default; guarded by SALUS_ALLOW_RESTORE=1 and blocked for multi-tenant full-database replacement.

## Reporting
- Server-generated printable executive HTML report.
- Executive CSV export.
- Existing JSON assessment package export retained.

## Validation
Fresh-database regression testing covered prototype and session modes, tenant isolation, spoofed-header resistance in session mode, evidence clearance filtering, assessment assignments, tenant-only backups, backup integrity verification, restore guard, executive HTML/CSV generation, Python compilation, and JavaScript syntax validation.

## Source integrity
The tested large source files are archived under source_archives/v0.5 and reconstructed by tools/reconstruct_v05_source.py.

- app.py SHA-256: 5572cf66373ecf906a1565a6f8d1e10cf3a294e24dbb79550f2cefef86fe06cf
- static/app.js SHA-256: 1a6dafabb637dc477143c3666d519f4d9d7ebe844fca067ee2566af373f5af8c
