# SalCAPA v3.112 — Governed demonstration-environment visibility

## Outcome

Authorized Salus evaluators can visibly inspect the Aster Ridge, Cedar Vale, and Northstar fictional demonstration environments through the ordinary SalCAPA interface.

## Controls

- Access is read-only and limited to authorized Salus evaluator roles.
- The authenticated server-controlled tenant and role never change.
- No fictional Protected Member persona is impersonated or permitted to sign in.
- Only the exact Issue #124 fictional fixture keys are returned.
- Cross-member records, tenant identifiers, credentials, and internal Salus information are not exposed.
- No approval, release, validation, decision, disclosure, or operational authority is created.
- All environments remain explicitly labeled as fictional demonstrations.

## Release boundary

This patch corrects the user-observed evaluation path without changing schema, weakening tenant isolation, or altering the accepted v3.111 rollback state. Azure promotion requires a separately governed immutable-image publication, deployment, and live authorized-evaluator acceptance.
