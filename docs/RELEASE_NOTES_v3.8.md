# SalCAPA v3.8 — Protected approval and branch-bound OIDC execution

## Outcome

The approved Azure development-foundation activation now separates protected human authorization from passwordless Azure execution. This preserves the GitHub environment gate while allowing the deployment job to use the already verified branch-bound federated identity.

## Controls

- An `authorize` job carries the `salcapa-dev-approval` protected environment and has no repository or OIDC permissions.
- The Azure execution job cannot start unless the authorization job succeeds.
- Only the execution job receives read-only contents access and the short-lived OIDC token permission.
- The activation remains restricted to the exact governed record on `development/salcapa-platform`.
- Two SHA-pinned checkouts verify the activation commit and exact frozen `release/v3.8` source without retaining credentials.
- The source commit must equal the frozen release head and be an ancestor of the activation commit.
- Live tenant, subscription, resource-group, constrained RBAC, what-if, cost, and no-Container-App controls remain fail closed.

## Failure containment

The preceding attempt passed record and frozen-source validation, then failed at Azure login because an environment-bound OIDC subject did not match the approved branch-bound federated credential. Azure provisioning never started and no resources were created.

## Delivery state

This candidate repairs approval/OIDC orchestration only. It does not itself provision resources, change DNS, create credentials, or perform a public cutover.
