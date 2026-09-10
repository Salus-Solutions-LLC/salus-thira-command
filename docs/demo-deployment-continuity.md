---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 10 September 2026 17:14 CDT
environment: azure_development_demonstration
deployed_release: v3.36
deployed_commit: 63d513605f908d3308bb5dd1bbdbf1061878452b
image_digest: sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46
deployed_at: 06 September 2026 13:18 CDT
deployment_workflow_run: 34051066468
deployment_acceptance: live_runtime_readiness_accepted
current_stable_release: v3.110
current_stable_commit: 935f0b7bea72375adc936f7904f4f74c2eb99643
promotion_candidate: v3.110
promotion_candidate_image_commit: 935f0b7bea72375adc936f7904f4f74c2eb99643
promotion_candidate_image_digest: sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44
promotion_candidate_image_reference: salcapadevb48224acr.azurecr.io/salcapa@sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44
promotion_candidate_image_published_at: 10 September 2026 17:14 CDT
promotion_candidate_image_workflow_run: 34536243545
promotion_candidate_image_acceptance: immutable_image_published_not_deployed
promotion_readiness: not_ready
fictional_member_seed_state: v310_image_published_not_deployed
critical_journey_acceptance: not_verified
rollback_baseline: v3.36
genuine_blocker: live_v336_database_entra_reporting_recovery_and_rollback_acceptance_missing
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the last verifiable Azure development demonstration deployment and the gates that control its next promotion. GitHub deployment records and successful workflow evidence control this record; conversation history does not.

## Last verifiable deployment

- The most recent successful governed application deployment is [workflow run 34051066468](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34051066468), completed on **06 September 2026 at 13:18 CDT**.
- The accepted runtime used frozen **v3.36** commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b) and immutable image digest `sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46`.
- The deployment workflow verified the immutable image, managed identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, readiness endpoint, required Azure dependencies, and Entra sign-in redirect. That acceptance did **not** establish the three fictional Protected Member environments or the full Issue #124 journey acceptance.
- No later governed application-deployment workflow run is recorded. The currently deployed version must therefore be treated as v3.36 unless a later Azure observation or deployment record proves otherwise.

## Stable-release comparison

The current stable product is **v3.110** at [`935f0b7bea72375adc936f7904f4f74c2eb99643`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/935f0b7bea72375adc936f7904f4f74c2eb99643). The demonstration materially lags the stable product and cannot yet represent its current user-visible capabilities.

The deterministic fixture foundation, bounded cross-functional records, and repository role/tenant preflight are verified. An exact-source rehearsal now also checks out frozen v3.36, preserves its governed baseline through current additive migrations, verifies an immutable report snapshot, adds all three fictional environments, and restores and rolls back one tenant without changing the others. The rehearsal passed on SQLite, PostgreSQL 16, and the production container. It did not contact Azure and does not represent human review, authorization, approval, release, or live deployment. The fixtures have not been applied to Azure.

The exact v3.109 source and image-packaging boundary is also verified. Frozen v3.109 does not contain the deterministic fixture capability, so that image remains a stable packaging reference rather than the complete Issue #124 promotion candidate. The successor work is now frozen as v3.110 after all 20 required workflow families passed on the exact release commit.

The immutable-image publication workflow is release-driven and fail-closed. It requires a separately governed activation whose release branch, exact commit, derived activation key, runtime release identity, immutable labels and non-root runtime agree before a push is permitted. [Validation PR #267](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/267) passed all 20 required workflow families on the exact v3.110 activation and was closed without merge.

[Publication workflow run 34536243545](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34536243545) then published exact frozen v3.110 as `salcapadevb48224acr.azurecr.io/salcapa@sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44` on 10 September 2026 at 17:14 CDT. It used workload identity and verified scoped registry authority. It created no mutable tag and performed no Container App deployment. Migration of an independently restored copy of the live accepted-v3.36 database, Microsoft Entra identity and tenant isolation, live reporting, Azure recovery, and Azure rollback acceptance remain required. The last accepted v3.36 deployment remains unchanged while those gaps are closed.

## Promotion gates

Before any newer milestone is promoted, all of the following must be verified on the exact frozen candidate and immutable image digest:

1. Forward schema migration from the accepted demonstration database and preservation of governed records.
2. Deterministic seed/reseed compatibility for Aster Ridge International Airport, Cedar Vale Energy Systems, and Northstar Applied Technologies, each visibly marked **FICTIONAL DEMONSTRATION**.
3. Microsoft Entra identity mapping, server-controlled role and tenant authority, disabled/unknown-user denial, and cross-tenant isolation.
4. Critical SalINTEL, SalTHIRA, SalCAPA, SalOPS, and cross-cutting PROVE journeys, including reports, exports, audit/version history, and reassessment.
5. Backup, recovery, and rollback rehearsal that preserves or restores the last accepted demonstration state if promotion fails.
6. Left-margin release display, day-month-year dates, 24-hour times, visual doctrine, Human-First Communications, Human Trust & Comprehension, and demonstration-only labeling.
7. A deployment record containing the promoted release, commit, immutable image digest, deployment time, workflow run, and acceptance result.

## Safety and authority boundaries

- Never place real Protected Member, employee, protectee, investigation, credential, or operational information in the demonstration.
- Seed and reseed operations must use normal application/domain rules or a separately governed fixture interface. They must not forge server-controlled lifecycle, provenance, approval, release, disclosure, audit, handoff, tenant, or calculated state.
- A failed preflight or promotion fails closed. It must not shift traffic away from the last accepted release or erase the accepted database.
- Reconfirm that the v3.36 immutable image remains available before relying on it for rollback. Database rollback uses an independently validated restore, not destructive in-place reversal.
- Promotion of the development demonstration does not authorize production cutover, DNS changes, new recurring cost, a higher Azure cost ceiling, or relaxed identity controls.

## Next authorized work

Validate migration of an independently restored copy of the accepted v3.36 database with exact frozen v3.110 and the published immutable candidate image under [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), without changing the running application or weakening frozen-source, immutable-digest, protected-environment, cost, identity, recovery, or rollback controls.
