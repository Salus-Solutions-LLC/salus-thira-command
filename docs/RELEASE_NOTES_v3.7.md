# SalCAPA v3.7 — Private-repository activation integrity repair

## Outcome

The approved Azure development-foundation activation now verifies its frozen source in a private repository without attempting an unauthenticated fetch after credentials are intentionally removed.

## Controls

- A second pinned `actions/checkout` step reads the exact `release/v3.7` source into an isolated path using only the job-scoped token.
- Both checkouts immediately discard persisted credentials.
- The activation record must name `release/v3.7` and its exact immutable 40-character commit.
- The isolated checkout head must equal the governed source commit.
- The source commit must also be an ancestor of the activation commit.
- Azure policy validation requires both pinned checkouts and rejects any post-checkout `git fetch`.
- The activation remains environment-protected, OIDC-only, resource-group-scoped, idempotent, and bounded by the approved USD 30 monthly ceiling.
- What-if and all pre-existing safety checks still execute before provisioning.

## Failure containment

The preceding activation attempt stopped during source validation before Azure login. It created no Azure resources and made no deployment changes.

## Delivery state

This candidate repairs the activation mechanism only. It does not itself provision Azure resources, change DNS, create credentials, or perform a public cutover.
