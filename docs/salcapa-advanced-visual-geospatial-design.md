# SalCAPA advanced geospatial and source-grounded visual-analysis design

**Status:** Approved bounded engineering design for the first Issue #236 implementation increment  
**Date:** 10 September 2026  
**Applies after:** SalCAPA v3.106  
**Parent requirement:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)

## Decision

The first Issue #236 implementation increment will make exact source-stored geospatial metadata and source-region-grounded visual observations native SalCAPA records. It extends the existing immutable-source, processing, provenance, tenant, sensitivity, disclosure, review, audit, backup, recovery, and server-controlled-state contracts rather than creating a parallel visual system.

The bounded implementation will:

1. preserve and parse authorized EXIF GPS facts from supported JPEG source material into a separate high-sensitivity metadata derivative;
2. let authorized Salus personnel review exact coordinates, their original component values, datum assumptions, capture-direction fields, altitude, source timestamp fields, and parser limitations;
3. let authorized personnel create structured image-region observations and prepare derived visual suggestions through one governed provider-neutral worker contract;
4. keep source-stored facts, directly visible observations, processing suggestions, analyst judgments, qualified findings, decisions, and approved disclosures as different record types and lifecycle states;
5. create proposal-only references into Facility Assessment, SalINTEL, SalTHIRA, SalOPS, Mission Map, and PROVE records;
6. preserve manual image and metadata review whenever a visual worker is unavailable, disabled, unaffordable, or not authorized.

This design does not cancel any broader Issue #236 capability. Object and condition classification, handwriting recognition, expanded and external OCR, maps and plans, additional image formats, and facial or biometric comparison remain authorized native SalCAPA capabilities. They will use the same contracts through separate bounded implementation and validation gates.

## Human and operational purpose

Salus personnel need to understand where an authorized image may have been created and what visible conditions it may document without losing source context or handing consequential judgment to a processing worker.

The first lifecycle is:

Original image → restricted location-metadata review aid and/or image-region review aid → Awaiting Human Review → Human Reviewed, Corrected, or Rejected → optional governed reference proposal → destination authority review

A person may compare a review aid with the original, correct its representation, explain uncertainty, and decide whether to propose a reference. Reviewing a derivative confirms only whether the representation is usable for the stated purpose. It does not authenticate the image, prove the depicted location or time, identify a person or object, establish evidence, qualify intelligence, create a SalTHIRA finding, authorize an operation, approve a plan, establish a cost or charge, or authorize disclosure.

Customer-facing and analyst-facing cues will use familiar actions such as **Review Location Metadata**, **Identify Visible Conditions**, **Review Source Region**, **Prepare Reference**, and **Recommended Next Step**. They must never say or imply that Salus personnel reviewed, verified, identified, approved, or decided something when only a worker produced a suggestion.

## Native record boundaries

### Immutable source material

The original image bytes, hash, source version, tenant, sensitivity, disclosure posture, acquisition details, and existing record lifecycle remain authoritative and unchanged. No derivative may replace the original or lower its restrictions.

### Restricted location-metadata derivative

A successful parser may create a distinct **Location Metadata — Source-Stored and Unverified** derivative containing only approved parsed fields and exact lineage to the source tags. Exact coordinates are not copied into ordinary OCR text, general search indexes, notifications, logs, exports, or low-sensitivity summaries.

The derivative records:

- original GPS tag identifiers and bounded source values;
- normalized latitude and longitude when all required components are valid;
- coordinate reference assumption, including WGS 84 only when supported by the source format and parser contract;
- altitude and altitude reference when present and valid;
- image direction and direction reference when present and valid;
- GPS date/time fields separately from image capture and ingestion times;
- missing, contradictory, malformed, truncated, out-of-range, or unsupported fields;
- parser, library, worker, configuration, and source-version identity;
- the transformation rationale for every normalized value;
- tenant, purpose, sensitivity, disclosure posture, access policy, lifecycle, and review status.

Absence of metadata is recorded as **Location Metadata Not Present**. Incomplete or contradictory fields are recorded as **Location Metadata Incomplete — Human Review Needed**. SalCAPA must never fabricate, geocode, reverse-geocode, interpolate, infer, or borrow coordinates to fill missing source metadata in this bounded increment.

### Image-region review aid

An image-region review aid associates a bounded pixel region or the full image with a proposed description or configured operational category. The source region uses coordinates tied to the original decoded image dimensions and records any orientation transform used for display. Cropped or rendered views are temporary review surfaces, not replacement sources.

The record distinguishes:

- **Visible Observation — Unverified:** a literal description of visible pixels without asserting hidden cause, identity, intent, authenticity, code compliance, structural integrity, threat, or event truth;
- **Processing Suggestion — Derived and Unverified:** a worker-prepared label or description that requires human comparison with the source;
- **Analyst Observation:** a named authorized person's recorded professional observation, retaining the worker suggestion and any correction;
- **Qualified Finding or Judgment:** a separate destination-domain record created only under that domain's authority and validation rules;
- **Approved Disclosure:** a separately released representation whose audience and exact content were authorized.

The first implementation must support person-entered visible observations even when no visual model is enabled. A provider-neutral worker interface may prepare suggestions only when a server-controlled processor profile is enabled and authorized. No processor profile is enabled merely because an image exists or basic OCR fails.

### Governed reference proposal

A reviewed derivative may support a proposal to reference the source or reviewed observation from another SalCAPA domain. A proposal records the destination, purpose, source basis, uncertainty, proposed relationship, initiator, and required destination authority.

Accepting a proposal creates a reference according to the destination's rules. It does not copy unrestricted source content, change the source sensitivity, convert a suggestion into a finding, activate monitoring, alter an assessment, approve a plan, establish legal or operational authority, authorize member disclosure, or create a customer charge.

## Exact GPS protection and use

Exact location can expose residences, protected facilities, routes, personnel movements, staging areas, vulnerable infrastructure, or investigative activity. It therefore uses a dedicated high-sensitivity access policy in addition to tenant and role checks.

Every exact-coordinate access must be evaluated server-side against:

- source tenant and source sensitivity;
- authorized role and named processing or review purpose;
- active scope and applicable investigative or operational authority;
- internal-use versus Protected Member disclosure posture;
- legal, contractual, privacy, retention, and records constraints recorded for the source;
- time-bounded access or purpose expiration where configured;
- export, reporting, mapping, and downstream-use permission.

Viewing exact coordinates creates a bounded audit event. Logs and ordinary audit summaries use the source record identifier and access outcome, not the coordinate value. Application errors must not echo coordinates. Cache keys, URLs, page titles, analytics, metrics, tracing attributes, notification bodies, and filenames must not contain coordinates.

A map or distance tool may consume exact coordinates only after the same policy check. Map placement and proximity results remain derived review aids. A point does not prove where the depicted subject, incident, person, or event was located. GPS time is not silently substituted for the event date. Direction is not silently treated as camera orientation or subject bearing without a supported field and explanation.

Protected Member output may use an approved generalized location, named facility reference, or separately approved exact point. Generalization creates a new governed derivative and never alters the exact source-metadata record.

## Visual observation and interpretation controls

The first visual-analysis contract is provider neutral. A processor profile is a server-controlled, versioned allowlist entry that defines:

- approved purpose and source categories;
- local or external execution boundary;
- model, provider, version, weights or artifact hash, runtime, and configuration;
- accepted formats, dimensions, regions, languages, and output schema;
- configured operational categories and prohibited conclusions;
- tenant, sensitivity, disclosure, jurisdiction, and legal/privacy eligibility;
- network endpoint and credential identity where applicable;
- retention, provider logging, data-location, and training-use rules;
- per-job resource ceiling, per-job cost ceiling, period spend ceiling, and fail-closed behavior;
- quality, bias, misuse, and validation evidence;
- effective date, expiration, approver, suspension, and supersession state.

The client may state a legitimate purpose and select an allowed image or region. It cannot choose an arbitrary provider, model, endpoint, prompt, executable, credential, confidence threshold, category set, data region, retention option, cost override, sensitivity override, or disclosure audience.

Worker output must conform to a bounded schema. Free-form text is stored only as a quoted processing suggestion with exact lineage and limitations. It may not issue instructions, trigger tools, modify records, select follow-on processing, activate monitoring, send communications, change scope, create findings, approve disclosures, or establish an identity or threat judgment.

The user interface must show the original image or an authorized source-linked view beside the suggestion, identify the supporting region when practical, explain that the suggestion is unverified, and offer **Confirm Representation**, **Correct**, **Reject**, or **Needs More Information**. It must not use a color as a generic truth, approval, investigation-tier, or completion indicator.

## Uncertainty and contradiction

Confidence supplied by a processor describes that processor's output under its own method. It is not probability that a real-world proposition is true, evidence weight, investigative confidence, readiness, risk, or a person's credibility.

SalCAPA records processor confidence only when the provider defines it and the value can be interpreted responsibly. The interface pairs it with plain-language limits and never reduces multiple observations to an unexplained overall score.

The system preserves:

- alternate labels or descriptions when returned;
- uncertainty about region, category, count, visibility, occlusion, image quality, and orientation;
- contradictions between source tags, visible context, prior records, and human observations;
- missing authority or context;
- known unknowns and information requiring field or partner confirmation.

A contradiction creates a review cue, not an automatic adverse conclusion. A corrected derivative appends a new version linked to the original worker output and reviewer rationale. It does not rewrite source metadata, original pixels, prior derivative versions, historical reviews, approved records, or released reports.

## Initial capability boundaries

The first implementation includes:

- supported JPEG source images already accepted under the v3.104 source and worker controls;
- fail-closed parsing of approved EXIF GPS fields;
- exact-coordinate normalization with source-component lineage;
- restricted exact-coordinate review;
- manual structured full-image and rectangular-region observations;
- provider-neutral storage and review contracts for later visual worker output;
- proposal-only downstream references;
- immutable corrections, rejection, supersession, audit, backup, and recovery.

The first implementation does not yet execute:

- geocoding, reverse geocoding, routing, clustering, heat maps, travel history, or inferred location;
- object detection, scene captioning, damage assessment, hazard classification, or visual question answering;
- handwriting recognition or expanded-language OCR;
- external OCR or visual-analysis transmission;
- floor-plan, map, diagram, engineering, structural, or code-compliance interpretation;
- face detection, face comparison, identity resolution, biometric template creation, emotion inference, demographic inference, or anonymous public-person search;
- video-frame analysis;
- automatic downstream findings, assessments, plan changes, monitoring activation, notifications, disclosure, billing, or operations.

These are bounded sequencing statements, not permanent product exclusions.

## Facial and biometric separation

Facial and biometric capabilities remain an authorized Issue #236 objective but must not share the ordinary image-processing permission. Their later module requires a separately approved lawful purpose, jurisdictional assessment, source and reference-set authority, high-sensitivity role, retention rule, disclosure rule, human review authority, model validation, quality limits, contradiction handling, access logging, deletion and legal-hold behavior, and cost architecture.

A future similarity result will remain a review aid. It cannot silently become identity proof, a threat judgment, an adverse decision, a cross-member match, or an approved disclosure. Unrestricted anonymous bulk search and default cross-Protected-Member correlation remain prohibited.

## External service separation

No source or derivative is sent externally in the first implementation. A later external OCR or visual provider requires an approved processor profile and explicit server-side eligibility. Local failure never authorizes external transmission.

Each external job must record the authorized purpose, source and derivative identifiers, exact transmitted representation hash, provider and endpoint, region, request and response times, retention/logging/training-use posture, service request identifier, response hash, actual or attributable cost when available, credential identity without secret material, and deletion or retention evidence where applicable.

Spend-ceiling, provider-availability, region, policy, or authorization failure leaves the source available for manual review. It does not weaken controls or silently choose another provider.

## Processing isolation and security

GPS parsing and visual workers run outside the web process through fixed entry points without a shell. They receive a read-only source or clean, bounded pixel representation and return schema-validated bounded output. They have a minimal environment, temporary workspace, resource limits, no user configuration, no client-selected executable, and no database, disclosure, billing, notification, or workflow authority.

The orchestrator verifies source hash, file signature, decoder allowlist, worker identity, output schema, value bounds, pixel-region bounds, tenant, sensitivity, purpose, and authorization before transactionally creating a derivative and audit evidence. A timeout, memory limit, malformed result, version mismatch, coordinate error, unauthorized tag, unexpected output, or worker failure creates no partial derivative and does not retry with weaker limits.

No source content or coordinate value may enter application telemetry, general logs, exception messages, crash reports, or third-party analytics.

## Azure and cost posture

The bounded first implementation uses request-driven processing within the established low-cost deployment posture. It introduces no standing GPU, new paid Azure AI service, queue, scale-out worker, duplicate permanent source store, or externally reachable processing endpoint.

The design permits future local or approved external visual processors through the same interface, but infrastructure is provisioned only after a separately reviewed identity, network, privacy, region, retention, procurement, operating-cost, and commercial-cost decision. Job cost is evidence for internal cost and commercial review; it never automatically changes scope, price, or customer charges.

If processing cannot fit the approved resource or spend ceiling, SalCAPA preserves original-image and manual structured review. The system remains usable without the worker.

## Integration boundaries

A reviewed location or visual derivative may support, through a governed reference proposal:

- SalINTEL source review, collection, hypothesis, contradiction, and qualified-intelligence work;
- Personnel Assessment without allowing a preliminary signal to become a judgment about a person;
- Facility Assessment observations, dependencies, controls, access, egress, equipment, and improvement needs;
- SalTHIRA hazards, threats, vulnerabilities, capabilities, consequences, and reassessment, while authorized people set priorities and decide;
- SalOPS planning, field operations, incident support, training, exercises, restoration, improvement, and validation;
- Mission Map source, facility, asset, event, dependency, and geographic relationships;
- PROVE evidence, accountability, results, traceability, learning, re-exercise, and assurance;
- Strategic Horizon Monitoring where later separately enabled;
- reports or the Protected Member common operating picture only after explicit release authorization.

PROVE remains cross-cutting and is not presented as a fifth product. SalCAPA coordinates governed information and action; it does not make human decisions. SalTHIRA identifies risk and establishes priorities; it does not coordinate operations.

## Data lifecycle, backup, and recovery

Source and derivative records retain tenant, sensitivity, disclosure, retention, legal-hold, correction, supersession, and deletion eligibility independently. An expired purpose may remove active access without rewriting historical audit evidence or an immutable approved version.

Portable backup and disaster recovery must restore:

- original source bytes and hashes;
- source metadata and restricted location derivatives;
- image-region definitions and coordinate systems;
- worker and processor-profile lineage;
- reviews, corrections, rejections, contradictions, and supersession;
- governed reference proposals and destination outcomes;
- access and processing audit evidence;
- policy and authorization versions needed to interpret historical decisions.

Recovery must not re-run visual processing silently. A restored derivative remains tied to the exact historical source and processor profile.

## Required implementation evidence

Before any release freeze, the candidate must prove:

- exact source-byte and source-hash immutability;
- correct parsing and normalization of valid north/south/east/west EXIF GPS examples;
- preservation of original rational components and transformation rationale;
- rejection of incomplete, contradictory, non-finite, zero-denominator, excessive, malformed, out-of-range, unexpected-datum, and unsupported tag values;
- no coordinate fabrication, borrowing, geocoding, inference, ordinary-search indexing, log leakage, URL leakage, notification leakage, or unauthorized export;
- tenant, role, sensitivity, purpose, disclosure, Protected Member, expired-authority, and cross-member denial;
- full-image and source-region traceability through orientation and display transforms;
- clear separation of source-stored fact, visible observation, processing suggestion, analyst observation, finding or judgment, and approved disclosure;
- manual observation and review when no model is configured;
- server-controlled processor profile, suspension, expiration, cost ceiling, and fail-closed behavior;
- immutable worker output plus append-only human correction, rejection, contradiction, and supersession history;
- no automatic identity, finding, threat judgment, assessment, priority, decision, plan approval, monitoring, disclosure, scope, price, charge, or operational action;
- proposal-only destination links and destination-specific authority checks;
- portable backup, exact restore, and no silent reprocessing;
- fictional demonstration fixtures only, with no personal, confidential, Protected Member, investigation, or licensed third-party imagery committed;
- SQLite and PostgreSQL 16 behavior;
- production-container operation under the unprivileged identity;
- deterministic reconstruction from reviewed artifacts;
- dependency audit, Bandit, repository hygiene, Azure policy and infrastructure validation, CodeQL, recovery, and all existing regression gates.

A controlled validation pull request must be closed without merge. The release may freeze only after every required gate passes on the exact candidate commit.

## Sequenced follow-on increments

After the first geospatial and visual-record contract is implemented and validated, Issue #236 should continue through bounded decisions for:

1. local source-grounded object and condition suggestions for approved operational categories;
2. handwriting recognition with source-region uncertainty and immutable human correction;
3. expanded local OCR formats and languages;
4. approved external OCR and visual providers with transmission and cost evidence;
5. map, plan, diagram, facility, route, proximity, and geographic relationship tools;
6. separately approved facial and biometric presence, quality, and authorized-reference comparison;
7. wider formats, video frames, advanced visual relationships, and performance scaling.

Each increment inherits the native records and controls in this design and receives its own dependency, quality, privacy, legal, security, cost, operational, and release validation.

## Product principle

**Preserve the source. Protect exact location and identity information. Show the source region and limits behind every review aid. Keep professional judgment, qualification, decisions, and disclosure with authorized people.**
