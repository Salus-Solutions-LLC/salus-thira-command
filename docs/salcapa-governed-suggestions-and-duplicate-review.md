# SalCAPA governed suggestions and duplicate review design

**Design date:** 09 September 2026  
**Roadmap issue:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131)  
**Candidate release:** v3.106  
**Status:** Approved bounded design; implementation and release validation remain required.

## Decision

The next SalCAPA material-processing increment will prepare tenant-scoped entity, date, time, and location suggestions and exact/near-duplicate review aids from authorized source derivatives.

The first implementation will run locally, on request, using server-controlled rules, approved tenant reference records, and bounded comparison methods. It will not call an external enrichment, geocoding, vector, language-model, identity, or data-broker service. It will not create an authoritative relationship or silently promote a suggestion into SalINTEL, SalTHIRA, SalOPS, PROVE, a Personnel Assessment, a Facility Assessment, Mission Map, Ongoing Monitoring, a report, a disclosure, or a commercial record.

## Operational purpose

Salus personnel need a disciplined way to notice possible names, organizations, facilities, assets, dates, times, places, repeated material, and related sources without manually rereading every derived representation.

This capability prepares review aids. An authorized person determines whether a suggestion is useful, corrects or rejects it, and decides whether a separately governed downstream action is appropriate. A matched string is not identity proof. A shared passage is not proof of common authorship, custody, coordination, intent, or truth.

## Human-first language

Analyst-facing actions use:

- **Review suggested references**
- **Review dates and times**
- **Review locations**
- **Compare sources**
- **Confirm as review aid**
- **Correct suggestion**
- **Reject suggestion**
- **Propose governed link**
- **Open original source**

The interface must not say that SalCAPA identified a person, verified a location, proved a duplicate, established a relationship, or made a decision when only local processing produced a candidate.

Every view shows the source basis, purpose, uncertainty, reviewer authority, current lifecycle state, and what happens next. It also explains that the analyst can stop and review the original source manually.

## Bounded first-slice scope

### Entity suggestions

The first slice may suggest references to:

- a person;
- an organization;
- a Protected Member;
- a facility or site;
- an asset;
- an event; and
- another approved tenant-scoped reference type.

Candidates come only from exact or bounded normalized comparison with already-authorized reference names and aliases available to the requesting tenant and role. The server, not the client, selects eligible reference types, fields, normalizers, minimum lengths, stop terms, and result limits.

The worker does not search public data, infer an unknown person's identity, enrich a person or organization, or compare one Protected Member's material with another member's reference records.

Each candidate retains the exact source text. Normalized comparison text is a processing aid and never replaces the source wording.

### Date and time suggestions

The first slice may recognize explicit, bounded source strings in approved patterns, including:

- day-month-year forms;
- unambiguous ISO dates;
- month-name dates;
- 24-hour times;
- explicitly marked timezone or offset forms; and
- deliberately flagged ambiguous numeric dates.

The record retains:

- the original source string;
- a proposed normalized value when supported;
- whether a year, timezone, or date order was assumed;
- every competing interpretation for an ambiguous value;
- the parser rule and version;
- the surrounding source span; and
- the display rendering in day-month-year and 24-hour format.

Relative expressions such as “tomorrow,” “next Friday,” or “two hours ago” remain unresolved in the first slice unless a separately stored, authoritative reference time makes the interpretation deterministic. Source and metadata dates are not treated as event dates merely because they appear near an event description.

### Location suggestions

The first slice may match source text against authorized tenant-scoped facility, site, address, municipality, region, and approved place aliases already stored in SalCAPA.

It must distinguish:

- text that names a place;
- a governed facility or address record;
- source-stored geospatial metadata;
- a depicted image location; and
- an analyst conclusion about where an event occurred.

Only the first two are in this increment. Exact GPS retention, coordinate access, mapping, proximity, routes, clustering, depicted-location reasoning, and external geocoding remain governed by Issue #236.

### Exact duplicate review

The system may state **Exact source-byte match** only when immutable source SHA-256 values are identical within the authorized tenant scope.

It may state **Exact derived-content match** only when derivative content hashes are identical and processor/format lineage is compatible.

An exact match does not prove that either source is authentic, complete, correctly attributed, current, independently collected, or suitable for the same purpose. Each source, version, retention rule, sensitivity, and disclosure posture remains independent. SalCAPA never deletes or silently merges originals.

### Near-duplicate review

The first slice supports bounded text near-duplicate suggestions for searchable textual derivatives. It does not perform image, face, audio, or video similarity.

Processing uses a deterministic server-controlled normalization and hashed token-shingle representation. Candidate generation and comparison are bounded by source size, token count, shingle count, candidate count, tenant, sensitivity authorization, and time. The exact algorithm, version, shingle width, thresholds, and limits are recorded.

A near-duplicate record includes:

- both source and derivative identifiers and hashes;
- comparison direction and scope;
- deterministic fingerprint method and version;
- bounded similarity measure;
- passages or shingles that support the comparison where safe to display;
- meaningful differences and truncation state;
- threshold and candidate-generation basis;
- uncertainty and non-proof warning; and
- independent review state.

Scores are comparison measures, not truth, reliability, threat, readiness, evidentiary weight, or identity confidence. User-facing views avoid false precision and use a plain description such as **Substantial text overlap — review both sources** with deeper technical detail available on demand.

## Relationship proposals

An analyst may use a reviewed suggestion to prepare a **Proposed governed link**. That proposal is a new, separately audited record. It does not modify either source or create an authoritative destination relationship.

A destination-specific authorized person must apply the existing rules for the target record. For example:

- SalINTEL qualifies intelligence and relationships;
- SalTHIRA identifies risk and establishes priorities while authorized people decide;
- SalCAPA coordinates information, decisions, and action;
- SalOPS implements, sustains, and improves protective capability; and
- PROVE provides cross-cutting evidence, accountability, results, validation, traceability, learning, and improvement.

The proposal cannot automatically open an investigation, assign an investigation tier, activate Ongoing Monitoring, create a threat judgment, update a Personnel or Facility Assessment, alter a plan, send a notification, disclose information, expand scope, or create a charge.

## Records

### material_suggestion_jobs

Records the bounded analysis request:

- tenant and source material;
- eligible derivative;
- legitimate purpose;
- requesting person and role;
- processor family, version, and rule-set hash;
- server-selected limits;
- status and failure code;
- start/completion timestamps;
- processing measurements; and
- audit references.

### material_suggestions

Stores each immutable initial suggestion:

- stable suggestion key;
- source material, version, and source hash;
- derivative, derivative hash, and processing job;
- suggestion type and subtype;
- exact source text;
- bounded before/after context;
- character span plus page, region, or time segment when available;
- proposed authorized reference, normalized date/time, or place reference when applicable;
- alternative candidates and ambiguity note;
- method, rule identifier, version, and quality indicator;
- tenant, sensitivity, purpose, and disclosure posture;
- lifecycle and review status;
- creation timestamp; and
- supersession link.

Initial state is **Derived — Unverified** and **Awaiting Human Review**.

### material_duplicate_suggestions

Stores exact and near-duplicate comparisons:

- stable comparison key;
- left and right source/derivative lineage;
- comparison class;
- method, version, rule-set hash, and thresholds;
- support and difference summary;
- truncation and limitation notes;
- comparison measure where meaningful;
- tenant and sensitivity authorization basis;
- lifecycle and review status; and
- creation and supersession timestamps.

The pair key is canonicalized to prevent duplicate comparison records without deleting either source.

### material_suggestion_reviews

Append-only review history records:

- suggestion or comparison identifier;
- prior and resulting state;
- review action;
- reviewer and role;
- review basis;
- corrected display value or selected reference, when authorized;
- rejected alternatives;
- timestamp; and
- audit reference.

Correction creates a reviewed value linked to the immutable original suggestion. It never overwrites the source text or the initial derived output.

### proposed_governed_links

Stores an optional handoff proposal:

- originating reviewed suggestion;
- proposed destination product and record;
- stated purpose;
- supporting source references;
- proposer and role;
- tenant, sensitivity, and proposed disclosure scope;
- status: Awaiting Destination Review, Accepted, Rejected, Withdrawn, or Superseded;
- destination reviewer/authority when acted upon; and
- timestamps and audit history.

Acceptance invokes the destination product's normal governed action. The material-processing module cannot accept its own proposal on behalf of another authority.

## Lifecycle

1. **Awaiting Human Review** — processing prepared the suggestion.
2. **Human Reviewed** — an authorized person confirmed the suggestion is usable as a review aid.
3. **Corrected** — an authorized reviewer supplied a linked correction while preserving the original.
4. **Rejected** — the candidate is not usable.
5. **Superseded** — a newer source, derivative, rule set, or review replaced its operational relevance while preserving history.
6. **Awaiting Destination Review** — a person prepared a governed-link proposal.
7. **Accepted / Rejected / Withdrawn** — the destination authority acted on the proposal.

Review does not promote source truth or evidentiary standing. A later source version creates new suggestions and may trigger review; it does not rewrite the historical basis for an approved record.

## Tenant, sensitivity, purpose, and disclosure controls

Every query begins with the authenticated tenant and server-resolved role. Source access, derivative access, reference access, comparison access, and destination handoff must each pass independently.

Controls include:

- no cross-tenant candidate generation, comparison, counts, timing hints, or error detail;
- no cross-Protected-Member comparison by default;
- source and reference sensitivity authorization before matching;
- result sensitivity at least as restrictive as the more restrictive input;
- purpose recorded before processing;
- Protected Member views limited to explicitly authorized released material;
- Salus-internal references and hidden metadata excluded from member-facing results;
- retention and legal-hold rules preserved independently for every source;
- disclosure separately authorized from internal review; and
- failed authorization indistinguishable from absence where revealing existence would be inappropriate.

## Processing controls

- Request-driven execution only.
- One bounded suggestion job per application instance in the first slice.
- Fixed server-side rules and thresholds.
- No client-provided expressions, code, model, executable, path, command, plugin, URL, provider, threshold, or index.
- No shell execution or network access.
- Unicode normalization preserves original text and records the normalization version.
- Strict maximum derivative size, token count, candidates, tenant references, comparisons, context length, output records, memory, time, and temporary storage.
- Failure produces no partial searchable suggestion or relationship.
- Source and derivative hashes are rechecked before commit.
- Re-running an identical job is idempotent and cannot multiply open suggestions.
- Search indexes and backup exports remain tenant scoped.
- Recovery revalidates lineage, pair canonicalization, review history, and destination proposal authority.

## Cost and Azure posture

The first slice uses the existing application and database allocation. It adds no paid API, vector database, search service, queue, GPU, standing worker, autoscale change, public endpoint, managed identity, secret, storage account, or external transmission.

Each job records bounded duration, input size, candidates considered, comparisons performed, and output count. If local limits are reached, SalCAPA explains **Review capacity unavailable — narrow the source set or review manually**. It does not silently add resources or charge a customer.

Any future semantic embedding, external enrichment, geocoding, vector search, paid language service, or cross-record model requires a separate architecture, privacy, data-location, procurement, security, model-governance, disclosure, identity, and cost review.

## Contextual guidance

Concise cue:

> Review proposed names, dates, places, and source similarities. These are source-review aids, not verified facts or authoritative relationships.

Deeper explanation:

> SalCAPA prepared these suggestions from authorized source-derived text and approved reference records. Open the original source, review ambiguity and differences, then correct, reject, or prepare a governed link for the appropriate Salus authority. Nothing is disclosed, monitored, billed, or promoted into an assessment, finding, plan, or decision by this review alone.

Exact duplicate cue:

> These records have the same source-byte hash. Review custody, version, purpose, sensitivity, and retention separately.

Near-duplicate cue:

> These sources contain substantial text overlap. Review both originals and the identified differences; similarity does not prove common authorship, truth, identity, or intent.

## Required validation

The implementation candidate must prove:

- exact source and derivative lineage;
- immutable original suggestions plus append-only correction history;
- tenant and Protected Member isolation for matching, counts, timing, search, and recovery;
- sensitivity and purpose enforcement;
- explicit and ambiguous date cases with preserved source wording;
- day-month-year and 24-hour display behavior;
- approved-reference matching without external lookup;
- exact duplicate detection by hash without record merge or deletion;
- bounded deterministic near-duplicate comparison with meaningful differences;
- no image, biometric, audio, video, or cross-tenant similarity in the first slice;
- no automatic destination relationship, monitoring, investigation, finding, assessment, plan, notification, disclosure, scope, charge, or authority;
- idempotency, failure atomicity, supersession, backup, reconstruction, and recovery;
- SQLite and PostgreSQL 16 parity;
- production-container execution under the unprivileged identity;
- dependency audit, Bandit, repository hygiene, Azure infrastructure policy, and CodeQL;
- all existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, planning, visual, reporting, date/time, and frozen-release regressions; and
- the complete integrated fictional analyst journey before final Issue #131 closure.

## Deferred work

Separately governed later increments include:

- image, diagram, map, plan, object, condition, handwriting, and scene-derived suggestions;
- exact GPS retention and spatial analysis;
- image, face, audio, or video near-duplicate comparison;
- facial or biometric detection, comparison, or verification;
- speaker separation or identity;
- external OCR, enrichment, geocoding, language, vector, or document-intelligence services;
- cross-Protected-Member correlation;
- automatic entity resolution or relationship qualification; and
- any paid standing processing infrastructure.

These deferrals preserve sequence and do not cancel the approved capabilities in Issue #236.
