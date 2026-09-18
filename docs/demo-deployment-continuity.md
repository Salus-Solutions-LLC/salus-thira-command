---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 18 September 2026 15:53 CDT
environment: azure_development_demonstration
deployed_release: v3.136
deployed_commit: 0eee07661658f229544317670c635568ce649bef
image_digest: sha256:e7a1a14af003806fa19875cb6ce13cef9e51c6c1f48338939ef7b174e39bc3a9
deployed_at: 18 September 2026 15:53 CDT
deployment_workflow_run: 35393259967
deployment_acceptance: full_demonstration_acceptance
current_stable_release: v3.136
current_stable_commit: 0eee07661658f229544317670c635568ce649bef
promotion_candidate: v3.136
promotion_candidate_image_commit: 0eee07661658f229544317670c635568ce649bef
promotion_candidate_image_digest: sha256:e7a1a14af003806fa19875cb6ce13cef9e51c6c1f48338939ef7b174e39bc3a9
promotion_candidate_image_reference: salcapadevb48224acr.azurecr.io/salcapa@sha256:e7a1a14af003806fa19875cb6ce13cef9e51c6c1f48338939ef7b174e39bc3a9
promotion_candidate_image_published_at: 18 September 2026 15:53 CDT
promotion_candidate_image_workflow_run: 35393259967
promotion_candidate_image_acceptance: immutable_image_deployed_and_accepted
promotion_readiness: accepted
fictional_member_seed_state: verified
critical_journey_acceptance: verified
rollback_baseline: v3.135
genuine_blocker: none
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the current accepted Azure development demonstration and its verified rollback. GitHub release branches, exact commits, immutable image digests, protected workflow results, and closed validation records control whenever another source disagrees.

## Current accepted deployment

- [Governed deployment and live acceptance workflow 35393259967](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35393259967) deployed and accepted exact frozen **v3.136** commit `0eee07661658f229544317670c635568ce649bef` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:e7a1a14af003806fa19875cb6ce13cef9e51c6c1f48338939ef7b174e39bc3a9`.
- Runtime readiness, immutable image identity, workload identity, Entra/OIDC, PostgreSQL, Key Vault, storage, telemetry, HTTPS, and exact-folder Microsoft 365 intake passed.
- The isolated Microsoft 365 acceptance execution succeeded. Its temporary Azure Container Apps job was deleted after acceptance and verified absent.
- Server-controlled role and tenant boundaries, cross-tenant denial, governed journeys, persistence, configuration preservation, and cleanup remain required controls.
- All seeded records remain clearly labeled **FICTIONAL DEMONSTRATION**. No real Protected Member information or human approval, decision, validation, or release is represented.

## Recovery and rollback

Accepted **v3.135** remains the fail-closed rollback baseline recorded by the v3.136 release acceptance.

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

Preserve exact accepted v3.124 and its v3.123 rollback while validating, freezing, publishing, and deploying v3.125, then verify the connector's administrative read-only status and exact-folder listing through the restored permanent hostname. Any additional source, write, report-publication, or production capability requires a separately governed successor.
