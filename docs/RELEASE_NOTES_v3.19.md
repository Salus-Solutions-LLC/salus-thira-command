# SalCAPA v3.19 release notes

## Exact PostgreSQL Entra administrator identity verification

- Verifies the temporary PostgreSQL administrator against Azure's documented `properties.objectId` field instead of the display resource `name`.
- Retains exact tenant ID, principal type, and principal name assertions.
- Includes the non-secret returned object ID in the bounded failure diagnostic.
- Adds Azure-policy source validation so the object-ID assertion cannot silently regress.
- Preserves passwordless authentication, immutable source/image selection, least-privilege runtime design, and convergent cleanup on failure.

No application deployment, DNS change, client secret, database password, or public cutover is performed by this release.
