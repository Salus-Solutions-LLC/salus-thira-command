# SalCAPA material processing acceptance and gap review

**Review date:** 09 September 2026  
**Roadmap issue:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131)  
**Reviewed releases:** v3.101 through v3.105  
**Decision:** Foundation accepted; Issue #131 remains open for two bounded capability increments and final acceptance.

## Purpose

This review compares the approved Issue #131 requirements with the immutable releases delivered through v3.105. It records what Salus personnel can rely on now, what remains unfinished, which work belongs in the existing issue, and which higher-sensitivity visual capabilities remain governed by [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236).

The review does not convert source-derived information into evidence, qualified intelligence, a finding, a threat judgment, a decision, a disclosure, or operational authority. People retain responsibility for interpretation, qualification, approval, release, and action.

## Acceptance decision

The material-processing foundation is accepted as stable enough to proceed:

- immutable source records and exact source hashes;
- separate derivatives with processor, version, method, timestamp, uncertainty, and lifecycle state;
- tenant, role, sensitivity, and disclosure boundaries;
- fail-closed processing without corrupting or replacing the source;
- request-driven local processing with manual fallback;
- human review that assesses the representation without asserting source truth;
- tenant-scoped search that returns reviewers to the source and review state;
- portable reconstruction, backup, validation, and recovery;
- SQLite, PostgreSQL 16, and production-container coverage;
- no standing paid processing service or silent scale-out.

Issue #131 remains open because entity/date/location suggestions and duplicate/relationship analysis were explicitly deferred by every bounded worker design and are not implemented in the current processing service.

## Delivered capability matrix

| Requirement area | Verified state | Release basis | Acceptance note |
| --- | --- | --- | --- |
| Inert text and structured files | Demonstrated | v3.101 | Text, CSV, TSV, JSON, XML, log, and EML extraction and scoped search are available. |
| Office documents | Demonstrated | v3.102 | DOCX, XLSX, and PPTX text and limited metadata are extracted without executing macros, formulas, objects, scripts, links, or remote content. |
| PDF embedded text | Demonstrated | v3.103 | Page-linked embedded text and limited metadata are prepared in an isolated process; OCR and rendering remain separate. |
| Image metadata and printed text | Partially Demonstrated | v3.104 | Bounded JPEG/PNG metadata review and English printed-text recognition are available. Advanced visual work remains in Issue #236. |
| Audio and video transcription | Partially Demonstrated | v3.105 | Bounded WAV, MP3, and MP4/AAC spoken-word review aids are available. Video frames, identity, and broader media interpretation remain separately governed. |
| Analyst review queue | Demonstrated | v3.101–v3.105 | Authorized reviewers can inspect, accept for representation review, or reject derivatives without promoting source truth. |
| Search | Demonstrated | v3.101–v3.105 | Search is tenant-, role-, and sensitivity-scoped and links results to the original source and review state. |
| Pluggable processing contract | Demonstrated | v3.101–v3.105 | Format workers reuse the governed source, derivative, review, search, audit, backup, and recovery contracts. |
| Entity/date/location suggestions | Evidence Needed | Not delivered | Current workers deliberately make no entity, resolved-date, or resolved-location proposals. |
| Duplicate and relationship analysis | Evidence Needed | Not delivered | Current workers do not propose exact/near duplicates or authoritative relationships. |
| Cross-format fictional demonstration | Partially Demonstrated | v3.101–v3.105 validation fixtures | Format-specific fixtures exist; a concise integrated analyst journey remains to be validated after suggestion and duplicate review are implemented. |

## Remaining Issue #131 work

### 1. Governed entity, date, and location suggestions

The next bounded design and implementation must prepare reviewable suggestions from authorized derived text without silently changing source meaning.

Each suggestion must retain:

- source material, version, and hash;
- derivative and processing-job lineage;
- exact quoted span or bounded source-region/time reference;
- proposed type: person, organization, facility, asset, event, date, time, address, or place;
- processor, version, configuration, and timestamp;
- recognition or extraction quality where meaningful;
- ambiguity, competing candidates, contradictions, assumptions, and unresolved context;
- tenant, role, sensitivity, purpose, and disclosure posture;
- lifecycle state and reviewer/correction history.

A suggestion must begin as **Derived — Unverified** and **Awaiting Human Review**. It must not become a qualified SalINTEL identity, Facility Assessment fact, Personnel Assessment conclusion, SalTHIRA finding, SalOPS authority, PROVE validation, Mission Map relationship, monitoring subject, or Protected Member disclosure merely because text resembles a name, date, or location.

Date handling must preserve the source wording. A normalized date or time is a proposal and must retain ambiguity, timezone basis, and the required day-month-year and 24-hour display conventions. Missing years, relative dates, local-time assumptions, and conflicting metadata remain explicit.

Location handling must distinguish a written place reference from source-stored coordinates and from the location depicted by an image. Exact geospatial metadata and spatial analysis remain in Issue #236.

### 2. Governed duplicate and relationship review

The following stages must be separate and explicit:

1. **Exact source duplicate:** same immutable byte hash within an authorized tenant scope.
2. **Exact derivative duplicate:** same derived-content hash under compatible processor and version lineage.
3. **Near-duplicate suggestion:** bounded similarity review aid with method, threshold, supporting passages or regions, and uncertainty.
4. **Relationship suggestion:** proposed connection among sources, people, organizations, facilities, assets, events, assessments, plans, or actions.
5. **Human-qualified relationship:** separately authorized action under the destination product's governing rules.

Exact equality may be stated when the compared hashes and scope support it. Similarity must never be described as identity, authorship, common custody, coordination, intent, threat, or proof.

Duplicate and relationship review must fail closed across tenants and Protected Members. It must not use hidden cross-member comparison, silently merge records, delete originals, consolidate retention schedules, change disclosure scope, create monitoring, create a commercial charge, or establish an investigative conclusion.

### 3. Integrated analyst journey

After the two capabilities above are implemented, the fictional demonstration environment must exercise:

- pasted text;
- structured data;
- Office material;
- PDF;
- photograph or map image;
- audio;
- video with an audio stream;
- an exact duplicate;
- a near-duplicate suggestion;
- an ambiguous person, date, and location suggestion;
- reviewer correction, rejection, supersession, search, backup, and recovery.

The journey must show purpose, source basis, uncertainty, review authority, what happens next, and how a person can stop without losing access to the original.

## Issue #236 boundary

The following approved capabilities are not rejected or canceled. They remain sequenced under Issue #236 after the current Issue #131 foundation and deployment/test baseline:

- exact GPS and broader geospatial metadata and analysis;
- image and scene interpretation;
- object and condition classification;
- handwriting recognition and broader OCR;
- approved external OCR or document-intelligence services;
- maps, plans, diagrams, and facility-image interpretation;
- separately governed facial and biometric functions.

Issue #131 may provide shared suggestion, provenance, review, duplicate, and relationship contracts for those later visual workers. It must not prematurely implement the legal, privacy, external-provider, identity, biometric, or cost decisions reserved to Issue #236.

## Next bounded increment

Prepare the design for governed entity/date/location suggestions and exact/near-duplicate review using local, request-driven processing first.

The design must define:

- stable records and lifecycle transitions;
- span, region, page, and time-segment provenance;
- server-controlled processors and thresholds;
- exact-hash comparison separately from similarity;
- ambiguity and contradiction handling;
- reviewer correction without overwriting the original suggestion;
- tenant, sensitivity, disclosure, retention, and purpose enforcement;
- downstream proposal-only handoffs;
- manual fallback and graceful degradation;
- low-cost deployment limits and per-job measurements;
- SQLite, PostgreSQL 16, production-container, reconstruction, recovery, dependency-audit, Bandit, repository-hygiene, Azure-policy, CodeQL, and regression validation.

The initial design must not introduce an external enrichment provider, paid standing service, vector database, unrestricted cross-tenant index, or automatic authoritative relationship creation.

## Final Issue #131 acceptance gate

Issue #131 may close only after:

1. the two remaining capabilities pass controlled release validation;
2. the integrated fictional analyst journey passes;
3. search and review remain scoped and source-linked across every delivered format;
4. backup, reconstruction, and recovery cover new records;
5. no suggestion silently establishes evidence, intelligence, identity, finding, decision, disclosure, scope, cost, or authority;
6. the continuity record identifies the next authorized Issue #236 or deployment-baseline increment; and
7. every frozen release and protected development line remains unchanged.
