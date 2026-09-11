# SalCAPA live-reporting acceptance

This critical-path gate verifies the exact frozen v3.111 report-release boundary against an independently restored copy of the accepted v3.36 development-demonstration database. It creates no application deployment, changes no traffic or DNS, and cannot modify the accepted database.

## Bounded purpose

The protected workflow binds the accepted v3.36 source, exact frozen v3.111 source, immutable image digests, hash-pinned acceptance script, fixed development environment, restore point, and temporary resource names. It then uses one temporary PostgreSQL restore and one non-ingress Consumption job. Both resources are removed after success or failure.

The exact v3.111 image exercises the application routes and database together. The isolated test proves that:

- Draft, Reviewed, and Approved report work remains unavailable to Protected Member roles;
- authorized lifecycle transitions must occur in order before delivery;
- Protected Member JSON, CSV, and printable HTML delivery uses the same immutable Released snapshot and SHA-256 identity;
- later changes to working assessment records do not silently alter the released member report;
- internal-only assessment fields remain excluded from member delivery;
- cross-member retrieval fails closed; and
- a changed snapshot that no longer matches its stored SHA-256 identity is denied and recorded as an integrity failure.

Named test identities and authority transitions exist only inside the temporary acceptance copy. They demonstrate the application boundary but do not represent actual Salus review, approval, release, customer communication, or operational authority.

The accepted application preservation check compares stable deployment configuration: immutable image, governed environment values, ingress, identity, scale, and absence of application secrets. Azure-managed audit timestamps are excluded because they may change independently of application configuration; the contract test prohibits those volatile fields from re-entering the comparison.

## Remaining gates

Successful isolated reporting acceptance does not establish Microsoft Entra user mapping, live tenant/role isolation through Entra sessions, Azure recovery, Azure rollback, application deployment, or end-to-end demonstration acceptance. Those gates remain separately required before v3.111 can replace the accepted v3.36 demonstration.
