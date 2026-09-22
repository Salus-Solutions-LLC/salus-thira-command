---
schema_version: 1
record_kind: salcapa_demo_deployment_continuity
last_verified_at: 22 September 2026 17:30 CDT
environment: azure_development_demonstration
deployed_release: v3.165
deployed_commit: 213e64b75301a2d623cbaa72a12f2fc87a58006a
image_digest: sha256:4f8dac192ff339efdf9c769e6d76283a431b654ed809b1ef652d4fe30359f60a
deployed_at: 22 September 2026 17:30 CDT
deployment_workflow_run: 35792094217
deployment_acceptance: full_demonstration_acceptance
current_stable_release: v3.165
current_stable_commit: 213e64b75301a2d623cbaa72a12f2fc87a58006a
promotion_candidate: v3.165
promotion_candidate_image_commit: 213e64b75301a2d623cbaa72a12f2fc87a58006a
promotion_candidate_image_digest: sha256:4f8dac192ff339efdf9c769e6d76283a431b654ed809b1ef652d4fe30359f60a
promotion_candidate_image_reference: salcapadevb48224acr.azurecr.io/salcapa@sha256:4f8dac192ff339efdf9c769e6d76283a431b654ed809b1ef652d4fe30359f60a
promotion_candidate_image_published_at: 22 September 2026 17:19 CDT
promotion_candidate_image_workflow_run: 35791492553
promotion_candidate_image_acceptance: immutable_image_deployed_and_accepted
promotion_readiness: accepted
fictional_member_seed_state: verified
critical_journey_acceptance: verified
rollback_baseline: v3.163
genuine_blocker: none
---

# SalCAPA development demonstration continuity

This non-sensitive engineering record identifies the current accepted Azure development demonstration and its verified rollback. GitHub release branches, exact commits, immutable image digests, protected workflow results, and closed validation records control whenever another source disagrees.

## Current accepted deployment

- [Governed deployment workflow 35792094217](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35792094217) deployed and accepted exact frozen **v3.165** commit `213e64b75301a2d623cbaa72a12f2fc87a58006a` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:4f8dac192ff339efdf9c769e6d76283a431b654ed809b1ef652d4fe30359f60a`; live readiness, Entra/OIDC, and isolated Microsoft 365 intake acceptance passed, and the temporary Azure test job was deleted.
- [Governed deployment workflow 35528377592](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35528377592) deployed and accepted exact frozen **v3.150** commit `7392fdd14f324b70889f77fe750a5c181a46e1d0` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:6fdf9abe3eb3a22b0fef96a12842cf0b25dc71e977870e73d0e0dd386292e7d9`; Protection Advisor live acceptance run `35528377626` passed, direct browser acceptance confirmed the repaired anonymous-review button invokes validation, Microsoft 365 acceptance passed, and the temporary Azure test job was deleted.
- [Governed deployment workflow 35525121006](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35525121006) deployed and accepted exact frozen **v3.149** commit `0da52e530304aba7c71ce8922009beb39c67ca2c` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:4a63c11a05ac85006dadb8aa21e8b6aab32a35863eb880a0afe21be5937912d0`; Protection Advisor live acceptance run `35525121029` attempt 2 passed, Microsoft 365 acceptance passed, and the temporary Azure test job was deleted.\n- [Governed deployment and live acceptance workflow 35484439351](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35484439351) deployed and accepted exact frozen **v3.143** commit `51370189b2518bb8fdf6614d34b593eb3d0fc989` as `salcapadevb48224acr.azurecr.io/salcapa@sha256:ee8ed8282c19473fa2a87d3526b61f7a2c6bd3f186e22f5e3c4f620cc5e8606b`.
- [Protection Advisor live acceptance workflow 35484772421](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/35484772421) verified the bounded Wix embed controls, visible Important Notice, and external Salus services navigation against the deployed runtime.
- Runtime readiness, immutable image identity, workload identity, Entra/OIDC, PostgreSQL, Key Vault, storage, telemetry, HTTPS, and correct-folder nested Microsoft 365 intake passed.
- Governed fail-closed extraction outcomes were preserved for human review. The isolated Microsoft 365 acceptance execution succeeded, and its temporary Azure Container Apps job was deleted and verified absent.
- Server-controlled role and tenant boundaries, cross-tenant denial, governed journeys, persistence, configuration preservation, and cleanup remain required controls.
- All seeded records remain clearly labeled **FICTIONAL DEMONSTRATION**. No real Protected Member information or human approval, decision, validation, or release is represented.

## Recovery and rollback

Accepted **v3.163** remains the fail-closed rollback baseline recorded by the v3.165 release acceptance.

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

Continue Issue #370 governed document ingestion and Protection Advisor usability work. Preserve v3.148 as the accepted rollback-safe baseline. Any expanded source, write, report-publication, or production capability requires a separately governed successor.
