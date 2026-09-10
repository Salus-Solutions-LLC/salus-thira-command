# SalCAPA object and visible-condition analysis design

**Status:** Approved bounded engineering design for the next Issue #236 implementation increment  
**Date:** 10 September 2026  
**Applies after:** SalCAPA v3.107  
**Parent requirement:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)

## Decision

The next Issue #236 increment will add local, source-grounded object and visible-condition suggestions as native SalCAPA review aids. It will extend the v3.107 immutable-source, image-region, processor-profile, provenance, tenant, sensitivity, disclosure, review, audit, backup, recovery, and governed-link contracts. It will not create a separate visual system or a parallel source of authority.

The bounded implementation will:

1. accept an authorized JPEG or PNG source already governed by SalCAPA;
2. let an authorized Salus user state a legitimate operational or investigative purpose and request review of the full image or a bounded source region;
3. run one server-approved, local, CPU-capable visual processor in an isolated request-driven worker with no network access;
4. return bounded candidate objects or visible conditions with source regions, category identifiers, processor scores where responsibly interpretable, alternatives, and limitations;
5. store each result as **Processing Suggestion — Derived and Unverified** with exact source, preprocessing, processor, category-vocabulary, and job lineage;
6. require an authorized person to compare a suggestion with the source and record **Confirm Representation**, **Correct**, **Reject**, or **Needs More Information** before any governed downstream reference can be proposed;
7. preserve person-entered observations and manual image review when the processor is unavailable, disabled, inappropriate, unauthorized, or outside a resource or cost ceiling.

No object or condition suggestion establishes identity, ownership, authenticity, cause, intent, criminality, danger, code compliance, structural integrity, security effectiveness, readiness, a threat judgment, a finding, an operational decision, or disclosure authority.

This increment does not cancel the remaining Issue #236 capabilities. Handwriting recognition, expanded and external OCR, map and plan interpretation, advanced damage or engineering analysis, additional models, video-frame analysis, and separately governed facial or biometric capability remain authorized native follow-on increments.

## Human and operational purpose

Salus investigators, analysts, planners, assessors, and field personnel often need to find and review visible details across photographs without losing the relationship to the original image. A processing worker can reduce search burden and help direct attention, but professional judgment determines whether a visible item is correctly represented, relevant, and suitable for use in a Salus work product.

The bounded lifecycle is:

Authorized source and purpose → local processing job → unverified source-region suggestions → human source comparison → confirmed representation, corrected, rejected, or needs more information → optional governed reference proposal → destination authority review

The interface will lead with familiar tasks such as **Identify Visible Conditions**, **Review Source Region**, **Compare with Original**, and **Prepare Reference**. Technical processor identity, scores, transforms, and hashes remain available through deeper provenance details. SalCAPA must not imply that a Salus person observed, reviewed, verified, approved, or decided something when only the worker prepared a suggestion.

## Capability boundaries

### Included source types

The first implementation accepts only the single-frame JPEG and PNG sources already supported by the governed image pipeline. The orchestrator verifies the immutable source hash, file signature, decoded dimensions, frame count, tenant, sensitivity, lifecycle, and processing authority before a job begins.

The user may select the complete decoded image or a rectangular source region. Source-region coordinates are recorded against the original decoded dimensions together with orientation and preprocessing transforms. A temporary normalized pixel representation may be created inside the worker boundary. It is not a replacement source and is deleted when the job ends unless a separately governed derivative is deliberately retained.

Scanned PDFs, animated images, multipage images, RAW camera formats, maps, plans, diagrams, video frames, and live streams are not processed by this bounded worker. These are sequencing boundaries, not permanent product exclusions.

### Initial operational category vocabulary

The processor uses a server-controlled, versioned category vocabulary. The initial vocabulary may contain supported neutral categories within these families:

- access and egress: door, gate, opening, stair, ramp, corridor, and barrier;
- protective and monitoring equipment: camera, sensor, fence, bollard, lock, and controlled-access device;
- fire and life safety: extinguisher, alarm device, detector, exit sign, emergency light, hose cabinet, and first-aid equipment;
- utilities and continuity: generator, electrical equipment, fuel container, water equipment, communications equipment, and temporary power equipment;
- transportation and movement: passenger vehicle, truck, bus, bicycle, aircraft, vessel, and material-handling equipment;
- protective equipment and signage: helmet, vest, respirator, other configured PPE, warning sign, directional sign, and assembly-point sign;
- visible environmental or facility indicators: standing water, smoke, flame, debris, obstruction, broken glazing, visible surface damage, open access point, and blocked passage;
- configurable Salus-reviewed categories for a documented member, facility, incident, assessment, exercise, or operational purpose.

A category is enabled only when the approved processor has validation evidence for that exact category and the category wording does not overstate what pixels can support. Unsupported categories remain unavailable rather than being approximated by a misleading label.

### Person-related boundaries

The ordinary object worker may support a neutral **person visible** category only when the approved profile and purpose permit it. It must not perform face detection, face comparison, identity resolution, gait analysis, demographic inference, emotion inference, credibility assessment, health inference, protected-characteristic inference, or behavior/intent labeling.

Labels such as suspicious person, hostile actor, criminal, trespasser, insider threat, armed person, vulnerable person, employee, owner, or authorized person require facts and authority beyond ordinary object detection and are prohibited worker conclusions. A visible handheld item must not silently become a weapon judgment. Person-related suggestions receive higher sensitivity and cannot be disclosed or correlated across Protected Members by default.

Facial and biometric functions remain isolated behind their separately approved Issue #236 governance module.

### Visible condition boundaries

A worker may describe a supported visible pixel pattern, such as **passage appears obstructed** or **surface damage may be visible**, only when the category contract and validation evidence support that wording. It must preserve qualifying language and identify the supporting region.

The worker must not infer hidden conditions, precise dimensions, material composition, structural stability, code compliance, maintenance adequacy, system operability, protective effectiveness, ownership, chronology, cause, intent, event truth, or future performance solely from an image. It cannot determine that an exit is legally compliant, a camera is functioning, a fire extinguisher is serviceable, a barrier is adequate, a building is safe, damage was intentional, or an image depicts a current condition without separate qualified review and evidence.

## Native record model

### Visual processing job

Each request creates an immutable job record containing:

- tenant, source material identifier, source version and SHA-256 hash;
- authorized purpose, requesting user and role, request time, and source sensitivity;
- full-image or selected-region coordinates against original decoded dimensions;
- orientation, resize, padding, color, normalization, and coordinate-remapping transforms;
- server-selected processor profile and exact profile snapshot;
- model artifact, weights, runtime, dependency, configuration, and category-vocabulary hashes;
- worker entry point, isolation limits, start and completion times, outcome, and bounded error code;
- measured duration, CPU time, peak memory where available, and attributable cost evidence;
- output count, truncation, suppression, and limit information;
- external-processing flag fixed to false for this increment;
- lifecycle, retention, disclosure, correction, and audit linkage.

The job cannot be edited into success, rerun with weaker limits, or silently transferred to another provider. A retry creates a new linked job with its own authority and lineage.

### Processing suggestion

Each candidate result is stored separately from person-entered visible observations. It contains:

- immutable job, source, processor-profile, model-artifact, configuration, and vocabulary lineage;
- stable machine category identifier and plain-language display label;
- source-region coordinates after verified inverse transform to original-image space;
- worker score and score semantics only when the profile defines them responsibly;
- alternate categories or ambiguity returned within the bounded schema;
- occlusion, truncation, small-region, low-resolution, orientation, lighting, and other quality limits where supported;
- initial status **Awaiting Human Review**;
- tenant, sensitivity, disclosure, retention, and purpose posture;
- immutable original output and append-only review, correction, contradiction, rejection, and supersession history.

The suggestion record must not use an unexplained overall image score or translate a processor score into real-world probability, evidence strength, readiness, risk, threat, credibility, or certainty.

### Human review and analyst observation

The requester cannot independently review the same suggestion. An authorized reviewer compares the identified source region with the original and records one of:

- **Confirm Representation:** the bounded label and region reasonably represent the visible pixels for the stated purpose;
- **Correct:** the reviewer records corrected label, region, count, or limitations while preserving the original output;
- **Reject:** the output does not reasonably represent the source or should not be used for the stated purpose;
- **Needs More Information:** image quality, context, authority, or other information is insufficient.

Confirming representation does not promote the suggestion into evidence, intelligence, a finding, an assessment result, a plan requirement, or an approved disclosure. A reviewer may create a separate **Analyst Observation** that cites the source and reviewed suggestion, states professional reasoning and uncertainty, and remains governed by the destination domain.

Batch review may reduce burden only when each selected suggestion remains individually visible, individually recorded, reversible through correction or supersession, and attributable to the reviewer and rationale. A single opaque **accept all** action is prohibited.

### Governed downstream reference

Only a human-reviewed or corrected representation may be proposed as a reference to SalINTEL, Personnel Assessment, Facility Assessment, SalTHIRA, SalOPS, Mission Map, PROVE, Strategic Horizon Monitoring, a report, or the Protected Member common operating picture.

The proposal records the exact reviewed representation, source basis, uncertainty, destination, purpose, initiator, disclosure posture, and required destination authority. Acceptance by the destination applies that domain's rules. It does not silently change the visual record, source sensitivity, investigation tier, scope, price, customer charge, monitoring state, plan version, finding, priority, decision, or release state.

## Processor profile and model supply chain

The first worker is local and request driven. It uses a CPU-capable model through a provider-neutral inference boundary. The deployment supplies an approved model artifact; the application never downloads weights at runtime.

An enabled processor profile must specify:

- approved purposes, source types, tenants or service contexts, and sensitivity ceiling;
- model format, architecture contract, artifact path, artifact hash, provenance, license, and approved use;
- inference runtime and dependency versions with hashes or locked packages;
- exact preprocessing and output-decoding contract;
- category vocabulary and mappings with version and hash;
- category-specific validation evidence and known limitations;
- image and region dimensions, job duration, memory, CPU, output-count, and concurrency ceilings;
- score interpretation, category thresholds, suppression method, and truncation behavior;
- prohibited categories and conclusions;
- quality, misuse, bias, security, privacy, records, and legal review evidence;
- effective date, expiration, approver, suspension, supersession, and rollback state;
- no-network boundary and external-processing flag;
- per-job and period cost ceilings.

The web client cannot select an arbitrary model, provider, artifact, endpoint, prompt, threshold, vocabulary, executable, cost override, or disclosure audience. Configuration changes are server-controlled, auditable, versioned, and prospective. Historical suggestions retain the exact profile snapshot that produced them.

Missing, mismatched, unapproved, expired, suspended, tampered, or unsupported model artifacts fail closed. SalCAPA remains usable through original-image and manual source-region review.

## Worker isolation and security

The worker runs outside the web process through a fixed executable path without a shell. It receives a read-only verified source and a bounded request manifest. It has a minimal environment, temporary working directory, no database credentials, no application token, no tenant-wide access, no outbound network, and no authority to write application records or invoke follow-on actions.

The orchestrator enforces:

- file signature, format, frame count, dimension, pixel, metadata, and source-size limits;
- immutable source-hash verification before and after any read needed for processing;
- profile, model, runtime, dependency, configuration, and vocabulary hash verification;
- source-region and transformed-coordinate bounds;
- subprocess duration, memory, CPU, file, process, and output limits;
- strict request and response schemas with no executable or tool-bearing content;
- maximum suggestions per category and job;
- tenant, sensitivity, purpose, role, scope, disclosure, retention, and cost eligibility;
- transactional creation of a completed job and its suggestions only after full validation.

Timeout, memory exhaustion, decoder failure, malformed output, non-finite value, invalid region, unexpected category, model mismatch, score error, output overflow, worker crash, policy failure, or cost-ceiling failure creates no partial suggestion set. Bounded technical evidence may be retained without source pixels, exact coordinates, client content, or secrets in logs.

Worker output is data, not instruction. It cannot trigger tools, request external research, alter permissions, create findings, send messages, activate monitoring, modify plans, approve disclosures, or select additional processing.

## Uncertainty, contradiction, and quality

Processor performance varies with category, scene, scale, occlusion, viewpoint, image quality, lighting, weather, compression, and the population represented in validation data. SalCAPA must make those limitations understandable without presenting false precision.

The interface will:

- show the original image or authorized source-linked view with the suggested region;
- use the category label and **Derived — Unverified** state as the primary cue;
- show processor score only in provenance detail with its profile-defined meaning;
- identify clipped, small, overlapping, occluded, ambiguous, or low-quality regions when the processor supports those indicators;
- preserve plausible alternatives instead of silently choosing certainty;
- let reviewers correct labels and regions without overwriting original output;
- distinguish a processing limitation from absence of an object or condition;
- avoid red, orange, amber, or green for generic truth, review, workflow, tier, or completion state.

No detection means only that the configured processor returned no bounded suggestion. It does not prove that an item or condition was absent. A contradiction between a suggestion, person-entered observation, source metadata, prior image, or field report creates a review cue and separate record; it does not automatically decide which source is correct.

## Privacy, sensitivity, and disclosure

Every job and suggestion inherits at least the source tenant and sensitivity. More restrictive category- or purpose-based handling may raise sensitivity. It cannot lower source restrictions.

Ordinary search may index only approved redacted labels and reviewed representations according to policy. Source pixels, face regions, exact coordinates, protected-facility detail, person-related regions, and unreviewed sensitive labels remain excluded from general search, notifications, URLs, analytics, metrics, crash reports, filenames, and unauthorized exports.

Protected Member views show only explicitly released representations. They do not expose processor configuration, Salus-internal reasoning, other-member information, hidden suggestions, unrestricted regions, or internal audit evidence. Cross-tenant and unauthorized cross-member comparison fails closed.

Retention, legal hold, correction, supersession, and deletion eligibility apply independently to source, job, suggestion, review, analyst observation, and disclosure records. Deleting an eligible derivative does not silently alter immutable approved versions or required audit evidence.

## Azure and cost posture

The bounded worker uses request-driven CPU processing within the established low-cost deployment posture. It adds no standing GPU, paid visual-analysis service, new public endpoint, always-on queue, automatic scale-out, or duplicate permanent source store.

Concurrency defaults to one bounded job per application instance. Server-controlled resource and period ceilings protect the approved Azure budget. A job records measured duration and resource evidence sufficient for later internal cost and commercial review. Actual processing cost never automatically changes scope, package, price, invoice, or customer charge.

If the approved local model cannot meet quality or resource needs, the system preserves manual review. External visual services require a separate approved design covering provider terms, data region, retention, logging, training use, credential identity, network controls, transmission evidence, actual cost, and explicit source eligibility. Local failure never authorizes external transmission.

## Integration boundaries

A reviewed suggestion or analyst observation may support:

- SalINTEL collection, source comparison, information gaps, contradictions, hypotheses, and qualified-intelligence work;
- Personnel Assessment only without allowing a preliminary signal to become a judgment about a person;
- Facility Assessment review of access, egress, controls, equipment, utilities, visible conditions, dependencies, and improvement needs;
- SalTHIRA review of hazards, threats, vulnerabilities, capabilities, consequences, and reassessment while authorized people establish priorities and decide;
- SalOPS planning, field verification, incident support, training, exercises, restoration, improvement, and revalidation;
- Mission Map source, facility, asset, event, dependency, and geographic relationships;
- PROVE evidence lineage, accountability, results, validation, learning, re-exercise, and assurance;
- Strategic Horizon Monitoring only when separately enabled;
- reports and the Protected Member common operating picture only after explicit release approval.

SalCAPA coordinates governed information and action; it does not make human decisions. SalTHIRA identifies risk and establishes priorities; it does not coordinate operations. PROVE remains cross-cutting rather than a separate fifth product.

## Backup, recovery, and graceful degradation

Portable backup and disaster recovery preserve:

- immutable source identifiers, versions, hashes, and stored bytes;
- job requests, purposes, source regions, transforms, outcomes, resource evidence, and bounded errors;
- exact processor-profile, model-artifact, configuration, dependency, and vocabulary snapshots;
- immutable original suggestions and source-region mappings;
- human reviews, corrections, contradictions, rejections, and supersession;
- analyst observations and governed reference proposals;
- tenant, sensitivity, disclosure, retention, legal-hold, and audit evidence.

Recovery validates all relationships and hashes without silently re-running inference. Restored suggestions retain their historical processor lineage even when the active profile or model has changed. A missing current model does not make historical records invalid or unavailable for authorized review.

The manual source-region workflow remains available when processing is disabled, unavailable, degraded, outside authorization, or too costly. Users receive a clear bounded explanation and recommended manual next step rather than a false success or weaker automatic fallback.

## Required implementation evidence

Before a release freeze, the implementation candidate must prove:

- immutable original bytes and source hashes before and after processing;
- JPEG and PNG full-image and bounded-region operation;
- exact orientation, preprocessing, padding, resize, and inverse coordinate mapping;
- profile, model artifact, runtime, dependency, configuration, and category-vocabulary hash verification;
- local no-network subprocess isolation and unprivileged production-container operation;
- deterministic bounded outputs for approved fictional fixtures or a hash-pinned test artifact;
- rejection of malformed sources, unsupported formats, animated or multipage inputs, excessive images, invalid regions, unexpected categories, non-finite scores, invalid transforms, output overflow, timeouts, resource exhaustion, and tampered model artifacts;
- no runtime model download, external transmission, arbitrary provider or model choice, client-selected threshold, executable content, or tool execution;
- separate job, suggestion, review, analyst-observation, finding, decision, and disclosure states;
- **Derived — Unverified** and **Awaiting Human Review** default state;
- independent reviewer enforcement and immutable append-only correction, contradiction, rejection, and supersession history;
- neutral person-presence restrictions and absence of facial, biometric, demographic, emotion, credibility, identity, intent, or adverse-person inference;
- no automatic evidence, intelligence, finding, threat judgment, assessment result, priority, plan change, monitoring, notification, disclosure, scope, price, charge, or operation;
- no processor score presented as probability of real-world truth, evidence strength, risk, readiness, or credibility;
- no-output and low-quality states explained as processing limitations rather than proof of absence;
- tenant, role, sensitivity, purpose, scope, disclosure, Protected Member, cross-member, retention, expiration, suspension, and cost denials;
- ordinary-search, log, URL, notification, analytics, error, and unauthorized-export redaction;
- proposal-only destination linkage and destination-specific authority;
- exact portable backup, restore, hash and relationship validation, and no silent reprocessing;
- manual source-region observation and review when the processor is disabled or unavailable;
- fictional demonstration fixtures only, with no confidential, personal, Protected Member, investigation, or licensed third-party imagery committed;
- SQLite and PostgreSQL 16 parity;
- production-container validation under the established identity and deployment controls;
- deterministic reconstruction, dependency audit, Bandit, repository hygiene, Azure policy and infrastructure validation, CodeQL, recovery, and every existing regression gate.

A controlled validation pull request must be closed without merge. The release may freeze only after every required gate passes on the exact candidate commit.

## Sequenced follow-on increments

After this bounded object and visible-condition implementation is validated, Issue #236 should continue through separate decisions for:

1. handwriting recognition with source-region uncertainty and immutable human correction;
2. expanded local OCR formats and languages;
3. approved external OCR and visual providers with transmission and cost evidence;
4. maps, plans, diagrams, facilities, routes, proximity, and geographic relationship tools;
5. specialized damage, equipment, protective-control, and facility-condition profiles after category-specific validation;
6. separately approved facial and biometric presence, quality, and authorized-reference comparison;
7. additional image formats, video frames, advanced visual relationships, and performance scaling.

Each increment inherits the native source, provenance, human-authority, tenant, sensitivity, disclosure, audit, recovery, cost, and release controls in v3.107 and this design.

## Product principle

**Use processing to direct attention, not to replace professional judgment. Show the exact source region and limitations behind every suggestion. Preserve human authority over observations, findings, decisions, and disclosure.**
