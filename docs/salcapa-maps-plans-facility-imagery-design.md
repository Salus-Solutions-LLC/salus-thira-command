# SalCAPA maps, plans, diagrams, and facility-imagery design

**Status:** Approved bounded engineering design candidate for Issue #236  
**Date:** 12 September 2026  
**Applies after:** SalCAPA v3.112  
**Parent requirement:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)

## Decision

SalCAPA will add a governed, source-grounded way to review maps, floor plans, site plans, diagrams, schematics, annotated images, and facility photographs and to propose relationships to facilities, assets, rooms, areas, routes, controls, dependencies, damage, access or egress, hazards, and supporting evidence.

This capability will extend the existing material, visual-geospatial, object and visible-condition, handwriting, scanned-PDF, Facility Assessment, Mission Map, SalINTEL, SalTHIRA, SalOPS, and PROVE contracts. It will not create a parallel source store, silently process an entire member collection, or turn pixels, labels, scale marks, processing suggestions, or analyst annotations into verified engineering facts.

The normal lifecycle is:

Governed source → classify source representation and authority → select exact page or image region → inspect available text, visual, and geospatial facts → prepare a source-grounded relationship proposal → reconcile authoritative records, contradictions, assumptions, and information gaps → independent review → accept, correct, reject, or request more information → destination-specific governed reference → later qualification, decision, approval, release, or disclosure by the authorized human role

## Human and operational purpose

Plans and facility imagery help Salus personnel understand how places, functions, assets, routes, controls, and dependencies may relate. SalCAPA may reduce re-keying, keep analysts oriented to the exact source region, and make a proposed relationship easier to inspect. People remain responsible for deciding what the source represents, whether it is current and authoritative, whether labels and scale are dependable, what the information means, and whether it may support intelligence, assessment, planning, operations, assurance, or disclosure.

The interface will use familiar actions:

- **Review Plan or Image**
- **Select Source Region**
- **Review Visible Relationship**
- **Compare With Facility Record**
- **Record Assumption or Information Gap**
- **Prepare Facility Reference**
- **Accept, Correct, Reject, or Request More Information**

Before an action, SalCAPA shows the source, version, purpose, Protected Member, sensitivity, representation type, stated authority, date or unknown date, review status, proposed destination, and what happens next. It never claims human review merely because a local processor completed.

## Source classes and authority

Every source is classified without implying more authority than the record supports:

- **Authoritative Plan or Survey** — explicitly identified, current, controlled, and approved by the responsible owner or qualified authority for the stated use;
- **Controlled Organizational Record** — governed by the Protected Member or Salus but not necessarily authoritative for engineering dimensions, occupancy, code, or current field conditions;
- **Published Reference Map** — source and edition are known but fitness for the specific purpose still requires review;
- **Field Photograph or Survey Image** — records visible conditions from a stated place, direction, date, and recorder when those facts are available;
- **Annotated Working Copy** — contains proposals, notes, exercise marks, or other working information that remains distinct from the underlying source;
- **Diagram or Schematic** — represents relationships or concepts and may not preserve physical scale, distance, orientation, or construction detail;
- **Reported or Unverified Representation** — provenance, date, authority, scale, orientation, or completeness is missing or unresolved.

A source may have multiple characteristics, but SalCAPA records one primary class and every material limitation. Missing authority, revision, date, scale, north reference, legend, coordinate system, or site context is an explicit information gap. It is never silently supplied.

## Coordinate, scale, and geometry boundary

SalCAPA preserves exact coordinates and geometry when authorized and present. It also preserves the coordinate space in which each mark exists:

- immutable source page, frame, or image coordinates;
- PDF points and rendered-page pixels with exact forward and inverse transforms;
- decoded-image pixels and selected-region geometry;
- source-declared engineering or drawing coordinates;
- source-declared geographic coordinates and datum;
- governed WGS84 geographic features already accepted through the visual-geospatial path; and
- destination-specific Mission Map or Facility Assessment references.

A page-space or pixel-space mark is not a geographic coordinate. A drawing grid is not a surveyed coordinate system. A scale bar, stated dimension, north arrow, room label, route line, or symbol is recorded as source content until its meaning and authority are reviewed.

No pixel distance becomes a physical dimension unless an authorized person confirms an applicable source scale and its conditions. Perspective photographs, screenshots, diagrams, cropped plans, resized images, and photographed documents do not support precise dimensions merely because software can measure pixels. SalCAPA does not infer structural integrity, code compliance, occupancy, load capacity, concealed construction, hidden damage, legal property boundaries, or safe evacuation capacity from imagery alone.

## Native record model

### Representation profile

A server-controlled profile defines the permitted source types, page or image limits, coordinate behavior, local processors, approved purposes, sensitivity ceiling, review roles, cost limits, and graceful-degradation path. The profile is immutable by hash for each job and records provenance, version, license, known limitations, validation evidence, approver, effective and expiry dates, suspension, supersession, and rollback state.

The initial profile reuses approved CPU-capable local components. It downloads no runtime model or map, initiates no external request, and provisions no standing GPU or paid document, vision, geospatial, or biometric service.

### Source-region reference

Each reference records:

- tenant, governed material identifier, material version, immutable source SHA-256, and sensitivity;
- representation class, stated title, revision, date, author or issuer, authority basis, and known limitations;
- exact page or frame and source label where applicable;
- source-space polygon or bounded region and coordinate origin;
- rendered-page hash and PDF-point/rendered-pixel transforms when a PDF page is used;
- image dimensions, orientation, crop, scale, and other applicable transforms;
- geographic coordinates, datum, altitude, direction, precision, and provenance when already authorized;
- legitimate purpose, requester, role, request time, and destination under consideration;
- retention, legal hold, disclosure, correction, supersession, and audit linkage.

The reference points to immutable source bytes. It does not duplicate or replace the source.

### Prepared relationship proposal

A proposal may describe a possible relationship among a selected source region and one or more governed facility, asset, room, area, route, control, dependency, condition, hazard, incident, exercise, observation, plan, task, or evidence records. It records:

- proposal type and neutral operational description;
- source-region reference and exact supporting geometry;
- originating method: source-stated, local processing suggestion, analyst observation, reported information, or reconciled reference;
- processor, profile, model, vocabulary, configuration, and result lineage when processing assisted;
- alternatives, contradictions, uncertainty, limitations, assumptions, and information gaps;
- candidate target record identifiers without changing those records;
- review status, reviewer, correction history, and disposition;
- member visibility and disclosure posture fixed to not released until separately authorized.

Every proposal begins **Derived — Unverified** or with the applicable non-conclusive human epistemic state. A proposal is not an observation, finding, threat judgment, priority, plan requirement, task, engineering determination, identity conclusion, evidence ruling, disclosure, or release.

### Reconciliation and review record

A different authorized person compares the proposal with the exact source region and, where relevant, the current governed facility or destination record. The reviewer records:

- **Accept Representation** — the bounded source-region and stated relationship are represented accurately for the stated purpose;
- **Correct** — preserve the original proposal and append the corrected relationship or geometry;
- **Reject** — retain provenance but prohibit ordinary downstream use;
- **Needs More Information** — create or link a bounded information gap without guessing; or
- **Superseded** — link the later source or proposal without erasing history.

Acceptance confirms only the representation described by the review basis. It does not establish source authenticity, currency, engineering validity, legal authority, code compliance, structural condition, threat, priority, decision, approval, or disclosure authority.

## Representation-specific safeguards

### Maps and geospatial sources

SalCAPA preserves declared projection, datum, coordinate system, precision, edition, publisher, acquisition date, license, and geographic extent when available. Reprojection or transformation records the exact method, library or service, version, parameters, accuracy statement, and input/output geometry. A transformation does not improve source accuracy. Approximate, generalized, reported, or unknown locations remain labeled accordingly.

A source map may be related to Mission Map or Facility Assessment only through a governed proposal. Exact coordinates remain available to authorized users and are excluded from unnecessary logs, URLs, generic notifications, metrics, crash reports, and unauthorized exports.

### Floor plans, site plans, and schematics

SalCAPA distinguishes sheet number, revision, issue purpose, discipline, legend, scale, north reference, level, zone, room or area label, and stated dimension. It preserves conflicts among sheets, revisions, field conditions, and facility records. A schematic relationship is not treated as physical adjacency or measured distance unless the source explicitly supports that conclusion and the reviewer confirms its applicability.

Routes, exits, barriers, utilities, controls, assembly areas, and dependencies may be proposed for review. SalCAPA does not declare a route safe, accessible, code-compliant, current, authorized, or operationally feasible based on a plan alone.

### Facility photographs and field-survey imagery

A facility image records visible conditions only within the frame, time, viewpoint, quality, and source limitations. Device location or direction may be preserved when present and authorized; neither is fabricated. Absence from a frame does not prove absence from the facility. A visible-condition suggestion remains separate from an analyst observation and from a qualified Facility Assessment finding.

Sequences and panoramas preserve ordering and overlap when known but do not silently create a surveyed three-dimensional model or exact measurement.

### Annotated and marked-up sources

The underlying source, each annotation layer, author, timestamp, purpose, and revision remain distinct. Exercise injects, proposed routes, draft zones, handwritten notes, and reviewer corrections cannot overwrite or masquerade as the approved source. Removal or hiding of a display layer does not erase its governed history.

## Domain integration

A reviewed representation may prepare a governed reference for:

- **SalINTEL**, where qualified personnel may use source-grounded information in research, investigation, and intelligence development;
- **Personnel or Facility Assessment**, where the domain workflow determines whether information supports context, an observation, an information gap, or a qualified finding;
- **SalTHIRA**, which may use accepted source relationships to inform hazard, threat, vulnerability, capability, consequence, and reassessment work while authorized people establish priorities;
- **SalCAPA**, which coordinates Protected Members, information, decisions, and action without making those decisions;
- **SalOPS**, which may use released plan and facility references for preparedness, planning, exercises, incidents, field operations, restoration, training, and improvement;
- **PROVE**, which retains traceability, validation, results, contradiction, lessons, and improvement evidence across the lifecycle; and
- **Mission Map**, which may display authorized relationships with their exact source, status, sensitivity, uncertainty, and disclosure boundaries.

Destination acceptance creates a new attributable domain event. It never changes the originating source or converts a reviewed representation into a qualified finding or released fact by implication.

## Protected Member, tenancy, and disclosure controls

All source, derivative, proposal, review, destination, search, map, report, backup, restore, and audit access is server-derived and tenant-scoped. Protected Member views expose only information explicitly released to that member. They never expose another member’s plans, facility imagery, coordinates, assets, rooms, routes, security controls, dependencies, review queues, Salus-internal reasoning, processor details, audit records, or unreleased annotations.

Cross-member comparison is prohibited unless a separately authorized Salus enterprise-intelligence purpose and disclosure rule explicitly permits the particular governed information. No hidden cross-tenant image, coordinate, or facility index is available to ordinary search.

## Cost, provider, and deployment controls

The first implementation remains request-driven, CPU-capable, local, and bounded. It reuses approved source inspection, page rendering, recognition, visible-condition, and geospatial components. It creates no Azure deployment, standing worker, GPU, external tile request, paid geocoding, digital-twin service, photogrammetry service, external OCR, vision provider, or biometric service.

Any later external provider requires a separate approved route covering provider and product, contract and data-processing terms, allowed purpose and source classes, jurisdiction and data region, retention and training posture, workload identity, private networking or controlled egress, encryption, transmission receipt, validation set, failure handling, per-job and period spend limits, suspension, rollback, audit, and disclosure. Local failure never authorizes external transmission.

## Backup, recovery, and graceful degradation

Portable backup and recovery preserve source-region references; representation classes and authority; exact hashes, pages, frames, geometry, transforms, coordinates, scale facts, profiles, processors, proposals, alternatives, contradictions, uncertainty, assumptions, gaps, reviews, corrections, destination references, sensitivity, retention, legal hold, disclosure, and audit evidence.

Restore validates relationships and hashes without silently reprocessing, reprojecting, re-rendering, reinterpreting, or redownloading anything. Historical records remain reviewable when a profile or source edition is unavailable or superseded.

When processing, map display, transformation, or source rendering is unavailable, unauthorized, outside a resource limit, or too costly, SalCAPA preserves manual source review, coordinate entry, facility-record comparison, and printed or offline operating methods. The interface explains the limitation and does not imply the source lacks the information.

## Required implementation evidence

Before an implementation candidate may freeze, validation must prove:

- only active governed sources with matching immutable hashes enter the path;
- every reference is tenant-, role-, sensitivity-, purpose-, lifecycle-, and disclosure-scoped;
- source class, version, date, authority, scale, north, datum, projection, precision, and limitations remain explicit rather than fabricated;
- PDF page, rendered-page, source-image, pixel, drawing, and geographic coordinate spaces remain distinct and round-trip through recorded transforms;
- a source region cannot escape the page or image boundary;
- physical distance or dimension is unavailable without an applicable reviewed scale;
- perspective imagery, diagrams, screenshots, and photographed plans cannot silently produce precise engineering dimensions;
- no automatic structural, code, occupancy, hidden-condition, safe-route, threat, priority, identity, finding, decision, disclosure, or authority conclusion occurs;
- original sources, annotations, processor suggestions, analyst observations, reviews, corrections, and destination records remain distinct and append-only;
- proposals begin unverified, expose uncertainty and contradictions, and require independent review;
- rejected and unresolved proposals cannot enter ordinary governed search or downstream use;
- destination acceptance applies that domain’s authority and creates attributable history;
- exact authorized geographic coordinates remain usable while unauthorized search, logging, export, report, and member disclosure fail closed;
- cross-tenant, cross-member, insufficient-role, insufficient-clearance, expired-profile, suspended-source, tampered-source, stale-revision, and cost-ceiling cases fail closed;
- backup and restore preserve hashes, relationships, states, and historical profiles without reprocessing;
- graceful manual review and alternate operating capability remain available;
- no paid external route, standing GPU, map tile, geocoding, external OCR, vision, digital twin, photogrammetry, or biometric service activates;
- no confidential, personal, real Protected Member, investigation, credential, operational, or licensed third-party source content is committed; and
- fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, deterministic reconstruction, repository-hygiene, Azure-policy/infrastructure, CodeQL, recovery, and every established archived capability gate pass on the exact candidate.

The controlled validation pull request must be closed without merge. `main`, `development/v1.17`, `release/v1.16`, v3.112, and every earlier frozen release remain unchanged.

## Sequenced implementation increments

After this design checkpoint, Issue #236 proceeds in bounded steps:

1. source representation, authority, region, and relationship-proposal records using existing local components;
2. independent reconciliation, correction, search, backup, restore, and destination-reference controls;
3. Facility Assessment and Mission Map interface guidance and acceptance;
4. additional approved local layout, symbol, facility-condition, damage, equipment, and protective-control profiles where validation evidence justifies them;
5. separately authorized external document or geospatial routes only after contract, privacy, security, residency, validation, and spend gates; and
6. facial or biometric work only as a separately approved high-sensitivity module after explicit legal, privacy, contractual, operational, cost, and human-authority approval.

The design of the facial or biometric module remains preserved in Issue #236. This increment does not authorize its implementation or any public-person identification, bulk anonymous search, cross-member comparison, or paid biometric service.

## Product principle

**Keep the source authoritative. Preserve exact geometry and uncertainty. Make relationships inspectable. Let qualified people decide what the record means and what happens next.**
