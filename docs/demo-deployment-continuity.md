---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 11 September 2026 10:48 CDT
environment: azure_development_demonstration
deployed_release: v3.36
deployed_commit: 63d513605f908d3308bb5dd1bbdbf1061878452b
image_digest: sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46
deployed_at: 06 September 2026 13:18 CDT
deployment_workflow_run: 34051066468
deployment_acceptance: live_runtime_readiness_accepted
current_stable_release: v3.111
current_stable_commit: 8bf4614ec79a27641c40dc1a21e1790746a08604
promotion_candidate: v3.111
promotion_candidate_image_commit: 8bf4614ec79a27641c40dc1a21e1790746a08604
promotion_candidate_image_digest: sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311
promotion_candidate_image_reference: salcapadevb48224acr.azurecr.io/salcapa@sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311
promotion_candidate_image_published_at: 10 September 2026 21:10 CDT
promotion_candidate_image_workflow_run: 34553461921
promotion_candidate_image_acceptance: immutable_image_published_not_deployed
promotion_readiness: preflight_ready
fictional_member_seed_state: v311_live_copy_migration_accepted_not_deployed
critical_journey_acceptance: not_verified
rollback_baseline: v3.36
genuine_blocker: v311_deployment_and_three_member_acceptance_pending
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the last verifiable Azure development demonstration deployment and the gates that control its next promotion. GitHub deployment records and successful workflow evidence control this record; conversation history does not.

## Last verifiable deployment

- The most recent successful governed application deployment is [workflow run 34051066468](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34051066468), completed on **06 September 2026 at 13:18 CDT**.
- The accepted runtime used frozen **v3.36** commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b) and immutable image digest `sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46`.
- The deployment workflow verified the immutable image, managed identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, readiness endpoint, required Azure dependencies, and Entra sign-in redirect. That acceptance did **not** establish the three fictional Protected Member environments or the full Issue #124 journey acceptance.
- No later governed application-deployment workflow run is recorded. The currently deployed version must therefore be treated as v3.36 unless a later Azure observation or deployment record proves otherwise.

## Stable-release comparison

The current stable product is **v3.111** at [`8bf4614`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8bf4614ec79a27641c40dc1a21e1790746a08604). The demonstration materially lags the stable product and cannot yet represent its current user-visible capabilities. The exact stable image is published but remains non-deployed pending the remaining acceptance gates. The earlier v3.110 image is retained as immutable evidence and must not be promoted.

The deterministic fixture foundation, bounded cross-functional records, and repository role/tenant preflight are verified. An exact-source rehearsal now also checks out frozen v3.36, preserves its governed baseline through current additive migrations, verifies an immutable report snapshot, adds all three fictional environments, and restores and rolls back one tenant without changing the others. The rehearsal passed on SQLite, PostgreSQL 16, and the production container. It did not contact Azure and does not represent human review, authorization, approval, release, or live deployment. The fixtures have not been applied to Azure.

The exact v3.109 source and image-packaging boundary is also verified. Frozen v3.109 does not contain the deterministic fixture capability, so that image remains a stable packaging reference rather than the complete Issue #124 promotion candidate. The successor work is now frozen as v3.110 after all 20 required workflow families passed on the exact release commit.

The immutable-image publication workflow is release-driven and fail-closed. It requires a separately governed activation whose release branch, exact commit, derived activation key, runtime release identity, immutable labels and non-root runtime agree before a push is permitted. [Validation PR #267](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/267) passed all 20 required workflow families on the exact v3.110 activation and was closed without merge.

[Publication workflow run 34536243545](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34536243545) then published exact frozen v3.110 as `salcapadevb48224acr.azurecr.io/salcapa@sha256:c5f7b097a12589d3799205fa60e275afd020c4c41ec975eb175d54d04d4d7b44` on 10 September 2026 at 17:14 CDT. It used workload identity and verified scoped registry authority. It created no mutable tag and performed no Container App deployment. Migration of an independently restored copy of the live accepted-v3.36 database, Microsoft Entra identity and tenant isolation, live reporting, Azure recovery, and Azure rollback acceptance remain required. The last accepted v3.36 deployment remains unchanged while those gaps are closed.

[Live-copy migration workflow run 34545773447](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34545773447) completed successfully on 10 September 2026 at 19:29 CDT. It restored a 15-minute point-in-time copy of the accepted v3.36 PostgreSQL database, ran exact frozen v3.110 from the published immutable digest, applied additive migration and deterministic fictional fixtures, and verified three fictional environments, 24 governed personas, three Draft baseline assessments, and three cross-functional journey records. It proved that the source database and running application configuration were unchanged, then removed the temporary Container Apps job and restored database. This acceptance does not constitute deployment or traffic change. Microsoft Entra identity and tenant isolation, live reporting, Azure recovery, and Azure rollback acceptance remain required.

The next live-reporting gate correctly stopped promotion after proving that Protected Member roles could retrieve Draft report snapshots and mutable internal report previews. Frozen v3.110 and its published image remain unchanged and must not be promoted. The bounded v3.111 successor candidate makes report discovery and delivery release-gated: before release, Protected Members receive no report; after authorized release, JSON, CSV, and printable HTML are derived from the same immutable, hash-verified snapshot. Internal Salus previews remain available for review work. The accepted v3.36 application, traffic, and database remain unchanged.

All 20 required workflow families passed for the repair on exact candidate commit [`1582ae3`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/1582ae3898fd59d961d0494192e040828903107b), including the accepted-v3.36 migration rehearsal on SQLite, PostgreSQL 16, and the production container. [Validation PR #274](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/274) was closed without merge. All 20 families then passed again on final checkpoint commit [`8bf4614`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8bf4614ec79a27641c40dc1a21e1790746a08604), and [checkpoint PR #275](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/275) was closed without merge. That exact checkpoint is frozen as v3.111 and is not deployed.

[Publication workflow run 34553461921](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34553461921) published exact frozen v3.111 as `salcapadevb48224acr.azurecr.io/salcapa@sha256:6df0d41dd93fa929af33793d619630f41822a41ae91ed9d7050d074981fa0311` on 10 September 2026 at 21:10 CDT. Workload identity, scoped registry authority, exact frozen source, runtime release identity, non-root execution, and immutable digest checks passed. [Validation PR #276](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/276) passed all 20 required workflow families and was closed without merge before its exact head advanced to development. The workflow created no mutable tag, performed no Container App deployment, and changed no traffic or database state.

[Live-copy migration workflow run 34557442913](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34557442913) completed successfully on 10 September 2026 at 22:24 CDT. It restored a 15-minute point-in-time copy of the accepted v3.36 PostgreSQL database, ran exact frozen v3.111 from the published immutable digest, applied additive migration and deterministic fictional fixtures, and verified three fictional environments, 24 governed personas, three Draft baseline assessments, and three cross-functional journey records. Source-database and running-application configuration hashes remained unchanged, and the temporary Container Apps job and restored database were removed. [Validation PR #277](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/277) passed all 20 required workflow families on exact head [`e94ffd9`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/e94ffd9d55708df9513c4545227ed56dddc5c364) and was closed without merge before that commit advanced to development. This acceptance does not constitute application deployment, traffic change, identity acceptance, or release authority.

[Live-reporting workflow run 34605204344](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34605204344) completed successfully on 11 September 2026 at 08:49 CDT. Exact frozen v3.111 and its immutable image passed the report-release boundary against an isolated restore of the accepted v3.36 database: three fictional environments only, JSON/CSV/printable-HTML delivery, Draft exclusion, cross-member denial, immutable released snapshots, tamper rejection, workload identity, registry digest, accepted-database preservation, and running-application preservation. Temporary resources were removed. This establishes live reporting acceptance without deploying v3.111 or changing traffic.

[Microsoft Entra and tenant-isolation workflow run 34613330596](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34613330596) completed successfully on 11 September 2026 at 10:01 CDT. It verified the accepted v3.36 demonstration's tenant-specific Entra discovery, exact redirect, passwordless managed-identity client authentication, no-runtime-secret configuration, and anonymous-session denial. Exact frozen v3.111 and its immutable image then passed an isolated three-fictional-tenant exercise proving server-derived tenant, role, and clearance; cross-tenant audit isolation; and denial of unknown, disabled, foreign-tenant, invalid-issuer, invalid-audience, and replay cases. No interactive human login was represented. The accepted application, database, and traffic remained unchanged, and the temporary consumption job was removed. [Controlled validation PR #288](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/288) passed all 20 required workflow families on exact head [`22de9cc`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/22de9cc1841a136ce75acdb436fb7fb99b67ca36) and was closed without merge before that exact commit advanced to development.

[Azure recovery workflow run 34615239853](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34615239853) completed successfully on 11 September 2026 at 10:18 CDT. It bound the successful governed 15-minute point-in-time restore and exact-v3.111 migration evidence from run 34557442913 to fresh read-only verification of PostgreSQL recovery availability, versioned evidence retention, monitoring, budget controls, the accepted v3.36 application state, and the published immutable v3.111 image. It used workload identity, provisioned no resources, repeated no restore, and changed no accepted application, database, DNS, or traffic state. [Controlled validation PR #289](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/289) passed all 20 required workflow families on exact head [`aa1d008`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/aa1d0085ddff836ca9391d1fdefb585584f3d48a) and was closed without merge before that exact commit advanced to development. Recovery is accepted.

[Azure rollback workflow run 34617040315](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34617040315) completed successfully on 11 September 2026 at 10:48 CDT. Exact frozen v3.111 and its immutable image migrated an isolated 15-minute restore and established all three fictional environments. The temporary job was then replaced with exact frozen v3.36 and the accepted immutable image; that runtime successfully read the candidate-migrated database. Source-database and accepted-application state hashes remained unchanged, and the temporary job and restored database were removed. [Controlled validation PR #291](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/291) passed all 20 required workflow families on exact head [`a90c445`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/a90c445c594cb7ff68a66c4ebb11f6107af01ed0) and was closed without merge before that exact commit advanced to development. Every pre-promotion gate is accepted.

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

Promote exact frozen v3.111 and its immutable image through the governed Azure application deployment under [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), then perform end-to-end acceptance of the three fictional Protected Member environments. A failed promotion must preserve or restore the accepted v3.36 state.
