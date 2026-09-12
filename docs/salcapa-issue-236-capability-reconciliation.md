# Issue #236 capability reconciliation and governed completion boundary

**Status:** Governed reconciliation candidate  
**Prepared:** 12 September 2026  
**Authoritative roadmap:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)  
**Accepted deployed baseline:** SalCAPA v3.112  
**Decision authority:** Salus personnel retain legal, privacy, operational, disclosure, commercial, and release authority.

## Purpose

This record reconciles Issue #236 against exact accepted repository evidence. It separates:

1. capabilities that are implemented and demonstrated within approved boundaries;
2. capabilities whose governing design is accepted but whose route remains deliberately disabled; and
3. capabilities that remain preserved for later separately authorized implementation.

A deferred or disabled capability is not rejected, cancelled, or treated as unnecessary. Conversation history is not required to recover this state.

## Reconciled capability state

| Capability | State | Accepted evidence | Boundary |
|---|---|---|---|
| Exact GPS and geospatial source metadata | Demonstrated | Frozen v3.107 and controlled validation PRs [#243](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/243) and [#244](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/244) | Exact coordinates remain source-linked, tenant-, role-, purpose-, sensitivity-, and disclosure-controlled. Coordinates are not fabricated or copied into ordinary logs, URLs, notifications, or unauthorized exports. |
| Source-grounded image interpretation and object or visible-condition suggestions | Demonstrated | Frozen v3.108 and controlled validation PRs [#246](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/246) and [#247](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/247) | Suggestions remain Derived — Unverified, source-region linked, uncertainty-aware, and subject to independent comparison. No automatic adverse person or threat conclusion occurs. |
| Printed, handwritten, mixed, and targeted-region recognition | Demonstrated | Frozen v3.109 and controlled validation PRs [#249](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/249) and [#250](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/250) | The original derived output and correction history remain preserved. Recognition does not establish authorship, identity, credibility, intent, signature validity, or source truth. |
| Selected-page scanned-PDF rendering | Demonstrated | Controlled validation PR [#300](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/300) | Embedded text is inspected first. Only explicitly selected pages render locally under fixed limits. Ephemeral page bytes are deleted after validation while source and coordinate lineage remain. |
| Rendered-page recognition and independent review | Demonstrated | Controlled validation PR [#309](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/309) | Only hash-verified rendered pages enter the approved local recognition path. Prepared text remains unverified until a different authorized person compares it with the source. |
| Maps, plans, diagrams, and facility-imagery governance | Demonstrated | Design PR [#310](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/310), record PR [#312](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/312), coverage PR [#314](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/314), and interface PR [#316](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/316) | Source authority, revision, region, coordinate space, scale, limitations, alternatives, contradictions, information gaps, uncertainty, review, and destination authority remain distinct. Imagery alone cannot establish structural integrity, code compliance, occupancy, legal boundaries, or a safe route. |
| Local layout, symbol, condition, damage, equipment, and protective-control profiles | Demonstrated | Profile PR [#318](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/318) and interface PR [#320](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/320) | Six immutable server-controlled profiles are request-driven, local or manual, no-network, and human-reviewed. Profile preparation does not process source bytes or establish a finding or decision. |
| Governed downstream references | Demonstrated | Controlled validation PRs [#312](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/312), [#316](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/316), and [#320](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/320) | SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, Personnel Assessment, Facility Assessment, and Mission Map receive proposal-only references. Each destination applies its own authority, review, sensitivity, and disclosure rules. |
| Approved external OCR, document-intelligence, vision, geospatial, or mapping route | Designed — Disabled | [Handwriting and expanded-OCR design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-handwriting-expanded-ocr-design.md) and [maps, plans, diagrams, and facility-imagery design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/development/salcapa-platform/docs/salcapa-maps-plans-facility-imagery-design.md) | No automatic fallback or transmission is enabled. Provider, contract, privacy, residency, retention, training-use, identity, networking, validation, source-minimization, spend, suspension, rollback, audit, and disclosure approvals are prerequisites. |
| Facial and biometric module | Preserved — Separate authorization required | Issue #236 high-sensitivity requirements and the [advanced visual and geospatial design](https://github.com/Salus-Solutions-LLC/salus-thira-command/blob/developmentd/revelopment/salcapa-platform/docs/salcapa-advanced-visual-geospatial-design.md) | No biometric function is implemented or enabled. Lawful purpose, jurisdiction, legal and privacy assessment, authorized reference set, validation, sensitivity, retention, disclosure, cost, and explicit Salus authorization are prerequisites. Similarity must never become identity proof. |
| Additional languages, scripts, specialist models, forensic handwriting, and signature work | Preserved — Profile-specific validation required | [Handwriting and expanded-OCR design](https://github.com/Salus-Solutions-LLC/salus-thira-commandTokenizer=GPT4o/salcapa-handwriting-expanded-ocr-design.md) | These capabilities do not inherit authority from English and Latin-script recognition. Each requires approved artifacts, evidence, limitations, qualified review, and applicable legal or professional authority. |

## Issue #236 acceptance-criteria disposition

1. **Exact GPS metadata preserved and governed:** Demonstrated.
2. **Image interpretation and object or condition derivatives retain source-region provenance:** Demonstrated within the accepted bounded local path.
3. **Handwriting uncertainty and append-only correction:** Demonstrated.
4. **Approved external recognition only through explicit provider, data, and cost controls:** Control design accepted; route disabled pending complete authorization.
5. **Facial or biometric isolation and human review:** Requirement preserved; implementation not authorized.
6. **Cross-tenant and unauthorized cross-member access fails closed:** Demonstrated across SQLite, PostgreSQL 16, production-container, and accepted Azure identity and tenant-isolation gates.
7. **No derivative automatically establishes consequential authority:** Demonstrated and regression protected.
8. **Governed references into SalINTEL, SalTHIRA, SalOPS, and PROVE:** Demonstrated as proposal-only links; destination review remains separate.
9. **Immutable source and processor or profile lineage:** Demonstrated.
10. **Uncertainty remains explicit without false precision:** Demonstrated.
11. **Human-First and Human Trust & Comprehension doctrine:** Demonstrated in interface language and validation gates.
12. **Required release validation:** Demonstrated for each accepted increment through controlled PRs closed without merge.

## Current safe operating boundary

The accepted local capability is usable without a paid external processing service, standing GPU, public map-tile request, paid geocoder, photogrammetry service, digital-twin service, or biometric service. It preserves manual review and graceful degradation.

SalCAPA may preserve, inspect, render, recognize, compare, prepare, reconcile, and propose. It must not silently establish source authenticity, identity, authorship, intent, credibility, structural condition, code compliance, safe routes, findings, priorities, operational decisions, disclosures, customer obligations, commercial charges, or release approval.

## Deferred activation gates

### External-provider route

Activation requires one exact provider and product, approved source classes and purposes, governing contract and data-processing terms, jurisdiction and region, retention and training-use posture, workload identity, controlled networking, encryption, source minimization, transmission receipt, validation evidence, failure handling, per-job and period spend ceilings, suspension, rollback, audit, and disclosure rules. Local failure alone never authorizes transmission.

### Facial or biometric module

Implementation requires a separately approved high-sensitivity architecture and explicit Salus authority. The approval package must establish lawful purpose, jurisdictions, legal and privacy review, reference-set authority, prohibited uses, validation thresholds and limitations, qualified human review, contradictions and uncertainty, tenant isolation, retention, correction, disclosure, incident response, cost ceiling, suspension, rollback, and records obligations.

The following remain prohibited by default: unrestricted public-person identification, bulk anonymous face search, automatic adverse decisions, cross-Protected-Member face correlation, and treating similarity as identity proof.

## Recommended sequencing

1. Accept this reconciliation as the authoritative Issue #236 boundary.
2. Keep the external-provider and facial or biometric requirements preserved and disabled.
3. Do not provision or test a paid provider, GPU, or biometric service without explicit approval.
4. Resume the next approved low-cost roadmap increment that does not depend on these deferred authorities.
5. Reopen the relevant Issue #236 activation path only when its prerequisite approval package is complete.
6. Before any later freeze or Azure promotion, repeat the full required gate set and preserve v3.112 plus its tested rollback state.

## Demonstration decision

The accepted Azure v3.112 demonstration remains the maintained stable baseline. These later Issue #236 development increments have not yet been promoted as a coherent release. No Azure redeployment is justified by this reconciliation-only checkpoint.
