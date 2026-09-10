# SalCAPA immutable-image publication contract

This contract prepares an exact frozen SalCAPA release for controlled publication to the existing Azure development container registry. It does not authorize an application deployment, change traffic, alter the accepted demonstration, or approve a release for Protected Member use.

## Governed activation

Image publication occurs only when `deploy/azure/activations/image-dev.json` changes on `development/salcapa-platform` and the protected `salcapa-dev-approval` environment permits the job to proceed. A workflow or documentation change alone cannot trigger publication.

The activation record must identify one `release/v3.<number>` branch and its exact 40-character commit. Its activation key is derived from that release and commit. Unknown fields, a mismatched key, an unrecognized environment, or a commit that is not an ancestor of the activating development commit fails closed.

The accepted activation remains v3.36 until a separately validated activation explicitly identifies v3.110. Preparing this contract does not modify that record.

## Source and image identity

The workflow checks out the named frozen release, verifies its exact commit and clean state, and confirms the runtime release version matches the release branch. A new image receives immutable source-commit and release-version labels, runs as user 10001, and must report the same runtime version before it can be pushed.

Images use `source-<full-commit>` tags and are recorded by SHA-256 digest. The workflow does not create or update `latest` and does not deploy a Container App. Repeating an accepted activation resolves the already published digest rather than creating a different source identity.

## Azure boundary

Azure access uses workload identity federation. The workflow verifies the expected subscription, tenant, resource group, South Central US location, registry name, and scoped registry authority before publication. Client secrets are not used.

Publication is only one demonstration-promotion prerequisite. Live database-copy migration, Microsoft Entra identity and tenant isolation, reporting, recovery, rollback, and full journey acceptance remain separate gates. The running demonstration remains on the last accepted deployment until all applicable gates pass and a controlled application activation is approved.
