# SalCAPA Issue #131 final acceptance record

**Acceptance date:** 10 September 2026  
**Roadmap issue:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131)  
**Accepted release sequence:** v3.101 through v3.106  
**Current frozen release:** [v3.106 at `0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01`](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01)  
**Decision:** Accepted. [Controlled validation PR #239](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/239) passed all 17 required workflow families and closed without merge on 10 September 2026.

## Scope accepted

The bounded Issue #131 processing foundation is complete for:

- inert text, CSV, TSV, JSON, XML, log, and EML material;
- DOCX, XLSX, and PPTX material;
- PDF embedded text and page boundaries;
- single-frame JPEG and PNG metadata review and English printed-text recognition;
- PCM WAV, single-stream MP3, and MP4 with one AAC audio stream;
- tenant-scoped search and analyst review;
- authorized-reference, date, 24-hour time, and location suggestions;
- exact source-byte, exact derived-content, and bounded near-duplicate text comparison;
- proposal-only governed links;
- backup, reconstruction, integrity verification, and recovery.

The original source remains immutable. Each derivative remains separate and retains source hash, processor and version, method, timestamp, uncertainty, tenant, sensitivity, and review state. A processing failure does not alter or erase the source.

## Integrated fictional analyst journey

The controlled acceptance suite composes the fictional fixtures delivered with v3.101–v3.106 into one governed analyst journey:

1. Salus personnel submit pasted text, structured data, Office material, PDF material, a photograph or map-like image, audio, and video containing an audio stream.
2. SalCAPA preserves exact source bytes and hashes, performs only the format-specific bounded processing authorized for that source, and stores a separate **Derived — Unverified** representation.
3. A different authorized person reviews the representation. Review confirms the representation only and does not validate source truth.
4. Authorized search returns source-linked results within tenant, role, and sensitivity boundaries.
5. The source-review service prepares possible authorized references, locations, dates, and 24-hour times while preserving quoted context and ambiguity.
6. The suite exercises an ambiguous numeric date, independent correction without replacing the original proposal, a rejected or denied review path, an exact duplicate, and a bounded near-duplicate comparison.
7. A reviewed suggestion may create an **Awaiting Destination Review** link proposal. No authoritative relationship is created until the destination's governing authority acts.
8. Backup verification and disaster-recovery validation cover sources, derivatives, reviews, suggestions, comparisons, events, and link proposals.

The component fixtures are deliberately fictional and isolated. The larger three-Protected-Member demonstration population remains governed by [Issue #137](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/137); that broader demonstration does not reopen the completed processing-service scope accepted here.

## Release evidence

| Release | Verified capability | Controlled validation |
| --- | --- | --- |
| [v3.101](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/8d8c4e029a6612050fa697a6e1ee251761b8f61b) | Inert text and structured extraction, search, independent representation review | [PR #231](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/231), closed without merge |
| [v3.102](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/ab74673425de0b2c6a412382ad708220863879bb) | Non-executing Office Open XML extraction | [PR #232](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/232), closed without merge |
| [v3.103](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/459d7532d5eaa6e27c6facd6d39de55a7171837a) | Isolated PDF embedded-text and page-boundary extraction | [PR #233](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/233), closed without merge |
| [v3.104](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/a2e47f735a0267429f471455690cb22375f19ee9) | Isolated JPEG/PNG metadata and printed-text review | [PR #234](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/234), closed without merge |
| [v3.105](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/9b2e03144b1a68b64c4ce64b70536f63b47949ef) | Isolated local WAV/MP3/MP4 spoken-word review aids | [PR #237](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/237), closed without merge |
| [v3.106](https://github.com/Salus-Solutions-LLC/salus-thira-command/commit/0bdc7bc8ea3233794ef3ef3ced1c3293ab63bf01) | Governed suggestions, duplicate review, correction history, and proposal-only links | [PR #238](https://github.com/Salus-Solutions-LLC/salus-thira-command/pull/238), closed without merge |

The exact v3.106 candidate passed all 17 required workflow families, including SQLite, PostgreSQL 16, production container, dependency audit, Bandit, repository hygiene, Azure infrastructure, CodeQL, deterministic reconstruction, recovery, and regression checks.

## Authority and trust controls

The accepted capability does not automatically establish:

- source truth or authenticity;
- evidence or qualified intelligence;
- a person or organization identity;
- a Facility Assessment or Personnel Assessment conclusion;
- a SalTHIRA finding, priority, or decision;
- SalOPS command, policy, plan, or operational authority;
- PROVE validation;
- monitoring scope or activation;
- disclosure, commercial scope, cost, or customer charge;
- authorship, common custody, coordination, intent, or threat.

People retain qualification, interpretation, decision, approval, release, disclosure, and operational authority. The interface must continue to show purpose, source basis, uncertainty, review state, reviewer authority, and what happens next.

## Deferred capabilities remain authorized

Issue #131 completion does not reject or cancel advanced capabilities. [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236) preserves native SalCAPA requirements for authorized exact GPS and geospatial use, image and scene interpretation, object and condition classification, handwriting recognition, broader or approved external OCR, maps and floor plans, facility imagery, and separately governed facial and biometric capabilities.

[Issue #132](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/132), [Issue #136](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/136), [Issue #137](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/137), and [Issue #138](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/138) continue the parent Issue #128 connector, corpus-reuse, demonstration, and presentation work without recreating the completed Issue #131 processing foundation.

## Final gate

Issue #131 is accepted for completion. Controlled PR #239 passed every required workflow family and closed without merge. Frozen v3.106 and every earlier release remain unchanged.
