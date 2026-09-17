---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 17 September 2026 01:47 CDT
environment: azure_development_demonstration
deployed_release: v3.124
deployed_commit: 602b672828f2f6a1d24fc5b1e32cc36766d79ca8
image_digest: sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519
deployed_at: 17 September 2026 01:34 CDT
deployment_workflow_run: 35190102432
deployment_acceptance: full_demonstration_acceptance
current_stable_release: v3.124
current_stable_commit: 602b672828f2f6a1d24fc5b1e32cc36766d79ca8
promotion_candidate: v3.124
promotion_candidate_image_commit: 602b672828f2f6a1d24fc5b1e32cc36766d79ca8
promotion_candidate_image_digest: sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519
promotion_candidate_image_reference: salcapadevb48224acr.azurecr.io/salcapa@sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519
promotion_candidate_image_published_at: 17 September 2026 01:18 CDT
promotion_candidate_image_workflow_run: 35189223604
promotion_candidate_image_acceptance: immutable_image_deployed_and_accepted
promotion_readiness: accepted
fictional_member_seed_state: verified
critical_journey_acceptance: verified
rollback_baseline: v3.123
genuine_blocker: none
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the current accepted Azure development demonstration and its verified rollback. GitHub release branches, exact commits, immutable image digests, protected workflow results, and closed validation records control whenever another source disagrees.

## Current accepted deployment

- [Immutable-image publication workflow 35189223604](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35189223604) published exact frozen **v3.124** commit `602b672828f2f6a1d24fc5b1e32cc36766d79ca8` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:aaba6235b95f129ea8500bcb3f7a5e35bf576515794f5f2d7328bb82021d6519`. Exact source identity, runtime release identity, workload identity, scoped registry authority, immutable labels, and non-root execution passed.
- [Governed application-deployment workflow 35190102432](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35190102432) deployed that exact frozen source and immutable image. Workload identity, Entra-only PostgreSQL authentication, HTTPS ingress, bounded scale, required dependencies, runtime readiness, and the sign-in contract passed. Rollback was not invoked.
- [Live demonstration acceptance workflow 35191132113](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35191132113) accepted exact deployed **v3.124**. Aster Ridge, Cedar Vale, and Northstar, 24 non-authenticating fictional personas, server-controlled role and tenant boundaries, cross-tenant denial, governed SalINTEL/SalTHIRA/SalCAPA/SalOPS/PROVE journeys, PostgreSQL persistence, application-configuration preservation, and temporary-job cleanup passed.
- All seeded records remain clearly labeled **FICTIONAL DEMONSTRATION**. No real Protected Member information or human approval, decision, validation, or release is represented.

## Recovery and rollback

Exact accepted **v3.123** commit `4b976032fe2b8420ca2ec652ae7a7bfc5b130d87` and immutable image `salcapadevb48224acr.azurecr.io/salcapa@sha256:33b17998643d102b02dc998c409d96f743ec7d5bd8928f05efa999cf8c59b3be` remain the fail-closed rollback baseline.

Database rollback uses an independently validated restore, not destructive in-place reversal. A failed preflight, deployment, live acceptance, cleanup, readiness, identity, or tenant-isolation check fails closed and must preserve or restore the last accepted state.

## Promotion gates

Before any successor release is promoted, all required gates must pass on its exact frozen commit and immutable image digest:

1. Forward schema migration and preservation of governed records.
2. Deterministic fictional-fixture compatibility.
3. Microsoft Entra identity mapping, server-controlled tenant and role authority, unknown or disabled user denial, and cross-tenant isolation.
4. Critical SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, reporting, export, audit, and reassessment journeys.
5. Backup, recovery, rollback, and temporary-resource cleanup.
6. Accessibility, security, privacy, abuse resistance, Human-First Communications, and Human Trust & Comprehension checks.
7. A deployment record with the exact release, commit, immutable digest, workflow run, time, and acceptance result.

## Authority boundaries

- Never place credentials, secrets, real Protected Member, employee, protectee, investigation, or operational information in this record or the fictional demonstration.
- The application remains passwordless, uses managed identity, preserves bounded scale and the approved Azure cost ceiling, and changes no custom DNS.
- Acceptance of this Azure development demonstration does not authorize production cutover, public-data migration, expanded Microsoft 365 scope, report publication, or weakened identity, privacy, recovery, rollback, disclosure, provenance, or human-authority controls.

## Next authorized work

Preserve exact accepted v3.124 and its v3.123 rollback while verifying the deployed connector's administrative read-only status and exact-folder listing. Any additional source, write, report-publication, or production capability requires a separately governed successor.
