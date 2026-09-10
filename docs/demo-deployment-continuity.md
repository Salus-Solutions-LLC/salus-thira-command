---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 10 September 2026 12:25 CDT
environment: azure_development_demonstration
deployed_release: v3.36
deployed_commit: 63d513605f908d3308bb5dd1bbdbf1061878452b
image_digest: sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46
deployed_at: 06 September 2026 13:18 CDT
deployment_workflow_run: 34051066468
deployment_acceptance: live_runtime_readiness_accepted
current_stable_release: v3.109
current_stable_commit: 361a38300faddd7e9a93153c0629739acef870a0
promotion_candidate: v3.109
promotion_readiness: not_ready
fictional_member_seed_state: cross_functional_records_verified_not_deployed
critical_journey_acceptance: not_verified
rollback_baseline: v3.36
genuine_blocker: role_specific_journey_migration_recovery_and_rollback_acceptance_missing
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the last verifiable Azure development demonstration deployment and the gates that control its next promotion. GitHub deployment records and successful workflow evidence control this record; conversation history does not.

## Last verifiable deployment

- The most recent successful governed application deployment is [workflow run 34051066468](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/34051066468), completed on **06 September 2026 at 13:18 CDT**.
- The accepted runtime used frozen **v3.36** commit [`63d513605f908d3308bb5dd1bbdbf1061878452b`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/63d513605f908d3308bb5dd1bbdbf1061878452b) and immutable image digest `sha256:746a2e92cdc6e4189a772db65b1a3311b25be42ad65d0f6bc8e5779e86a58b46`.
- The deployment workflow verified the immutable image, managed identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, readiness endpoint, required Azure dependencies, and Entra sign-in redirect. That acceptance did **not** establish the three fictional Protected Member environments or the full Issue #124 journey acceptance.
- No later governed application-deployment workflow run is recorded. The currently deployed version must therefore be treated as v3.36 unless a later Azure observation or deployment record proves otherwise.

## Stable-release comparison

The current stable product is **v3.109** at [`361a38300faddd7e9a93153c0629739acef870a0`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/361a38300faddd7e9a93153c0629739acef870a0). The demonstration materially lags the stable product and cannot yet represent its current user-visible capabilities.

The deterministic fixture foundation and first bounded cross-functional records are verified in the repository. Each fictional Protected Member environment now stages collected but unvalidated SalINTEL information, low-confidence SalTHIRA working records, SalCAPA coordination and an awaiting-decision request, a requested but unauthorized SalOPS action, and PROVE evidence-needed, gap, and proposed-improvement states. No human review, decision, authorization, approval, release, or live deployment is represented. The fixtures have not been applied to Azure, and role-specific journey, migration, identity/tenant-isolation, reporting, recovery, and rollback acceptance remain required. The current deployment workflows also remain bound to the v3.36 activation contract. The last accepted v3.36 deployment remains unchanged while those gaps are closed.

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

Add and validate role-specific critical journeys and current-release migration preflight under [Issue #124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124), then generalize the promotion activation contract without weakening its frozen-source, immutable-digest, protected-environment, cost, identity, recovery, and rollback controls.
