# Governed Azure activation records

This directory contains explicit, reviewable one-time records that activate an already approved Azure operation from the governed development branch. It exists because the preserved default branch is not modified and therefore cannot host a newly added manual `workflow_dispatch` entry point.

## Foundation development record

`foundation-dev.json` is recognized only when all fields exactly match the enforced contract:

- schema version `1`;
- operation `foundation`;
- environment `dev`;
- location `southcentralus`;
- unique suffix `b48224`;
- approval record `MD-APPROVAL-AZURE-LEAN-20260904`;
- monthly authorization ceiling `30`;
- operational budget `25`;
- source release `release/v3.6`;
- source commit equal to the immutable head of that frozen release.

Unknown fields, a mutable or non-frozen source, a different resource scope, cost, region, suffix, operation, or approval record fail closed. The activation workflow also pauses at the protected `salcapa-dev-approval` environment, authenticates with GitHub OIDC, confirms resource-group-only authority, reruns Azure what-if, rejects deletes and premature Container App creation, and uses a deterministic deployment name.

Creating or editing this README never activates Azure. Only the exact path `deploy/azure/activations/foundation-dev.json` triggers the activation workflow.

## Prohibited contents

Activation records must never contain passwords, client secrets, tokens, connection strings, storage keys, database credentials, or personal authorization claims. They contain only governed non-secret identifiers and approval metadata.


## Database development record

`database-dev.json` is recognized only after the v3.14 bootstrap mechanism and image are frozen. It must identify the exact immutable release commit and registry digest, the fixed Salus tenant, and one or more pre-approved people by immutable Microsoft Entra object ID. Each mapping explicitly records the server-controlled username, display name, SalCAPA role, sensitivity clearance, and lifecycle status.

The protected workflow creates an in-network one-time Container Apps Job. Its temporary managed identity is an additional PostgreSQL Entra administrator only while the job creates the non-administrator runtime role and initializes the database. Cleanup removes the temporary administrator, job, and identity on both success and failure. Creating or editing this README never activates Azure.
