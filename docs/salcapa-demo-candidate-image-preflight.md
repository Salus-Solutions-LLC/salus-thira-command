# SalCAPA demonstration candidate-image preflight

**Recorded:** 10 September 2026 14:35 CDT  
**Issue:** [#124](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/124)  
**Accepted Azure baseline:** v3.36 at `63d513605f908d3308bb5dd1bbdbf1061878452b`  
**Current stable release:** v3.109 at `361a38300faddd7e9a93153c0629739acef870a0`

## Purpose

This preflight proves that a local container can be reconstructed from the exact frozen v3.109 source and labeled with its source commit and release. It does not publish an image, contact Azure, deploy an application, change traffic, change cost, or authorize release.

## Verified boundary

Frozen v3.109 predates the deterministic Issue #124 fixture capability. It does not contain `salcapa_demo_fixtures.py`, its reconstruction entrypoint, or the fixture workflow. The exact v3.109 image is therefore a governed reference for current stable product packaging, but it cannot by itself satisfy the maintained-demonstration requirement.

The next deployable demonstration candidate must be a separately frozen successor release that includes the already verified fictional-environment fixtures, role and tenant preflight, and accepted-v3.36 migration and recovery rehearsal. That successor must pass every required validation family before an immutable image is published or Azure is changed.

## Fail-closed controls

- The accepted v3.36 image and application activation records remain unchanged.
- The reference contract records `publish_authorized`, `deploy_authorized`, `traffic_change_authorized`, and `cost_change_authorized` as false.
- The preflight checks the exact frozen commit and pinned Git blob identities for the Dockerfile, runtime composition, and dependency manifest.
- The locally built image must run as the non-root `salus` user and report SalCAPA v3.109.
- A workflow artifact records the local image identifier for traceability; it is not a registry publication or deployment approval.
- No real Protected Member, personnel, protectee, investigation, credential, or operational information is used.

## What happens next

Prepare and validate the successor demonstration release candidate containing the governed Issue #124 capabilities. Only after it is frozen and every environment-bound migration, Microsoft Entra, tenant-isolation, reporting, recovery, rollback, and live acceptance gate passes may the demonstration move beyond accepted v3.36.

## Validation result

[Controlled validation PR #262](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/262) passed all 20 required workflow families on exact head `c886134cce96eb84f6e4c6896dd9ea5d6c46ab6a` and was closed without merge. The accepted Azure v3.36 activation records remained unchanged.

The successor development candidate then passed all 20 required workflow families on [controlled checkpoint PR #263](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/263) at exact commit `935f0b7bea72375adc936f7904f4f74c2eb99643`. That pull request was closed without merge, the same exact commit passed all 20 development-branch workflow families, and it was frozen as `release/v3.110`. No Azure resource or activation record was changed by the freeze.
