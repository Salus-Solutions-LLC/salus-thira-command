# SalCAPA live-copy migration acceptance

This governed acceptance path verifies that exact frozen SalCAPA v3.110 can migrate an independently restored copy of the accepted v3.36 development-demonstration database. It does not change the running application, its traffic, its database target, or the accepted database.

## Authority and activation

The workflow is inert until `deploy/azure/activations/live-copy-migration-dev.json` is added or changed on `development/salcapa-platform`. The record must bind the operation to the accepted v3.36 release, exact commit and image digest; the frozen v3.110 release, exact commit and published immutable image digest; the fixed development resource group, region, source server, temporary restore-server name, 15-minute restore point, approval record, revision, and activation key. Unknown fields or mutable identifiers fail closed.

The protected `salcapa-dev-approval` environment must permit the operation before GitHub exchanges its workload identity for Azure access. No password, database credential, client secret, storage key, or Protected Member information is stored in the record or workflow.

## Bounded operation

The accepted source server and running application configuration are recorded before the exercise. The workflow then:

1. creates a point-in-time restore with a different fixed server name;
2. verifies PostgreSQL 16, Microsoft Entra authentication, disabled password authentication, and private network access;
3. verifies that the frozen v3.110 digest exists in the governed registry;
4. creates one temporary, non-ingress Container Apps Job with the existing runtime managed identity and the exact immutable v3.110 image;
5. points that job only to the restored server, allowing normal application initialization to apply additive migrations;
6. prepares the three Issue #124 fictional demonstration environments through the governed fixture interface;
7. verifies the expected environment, persona, assessment, journey, Draft-state, and demonstration-label results;
8. rechecks the accepted source server and running application configuration; and
9. removes the temporary job and restored database on success or failure.

The v3.110 runtime receives no source-database hostname. The running application receives no restored-database hostname. A failure cannot deploy an application, shift traffic, change DNS, replace the accepted database, or promote the candidate.

## Evidence and remaining gates

A successful run records the workflow run, exact commits and digests, restore scope, fixture counts, source/application no-change checks, and cleanup result. It establishes live-copy schema and fixture compatibility only. Live reporting, Azure recovery and rollback, Microsoft Entra user/role mapping, live tenant isolation, and critical-journey acceptance remain separate gates before promotion.

