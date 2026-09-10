# SalCAPA handwriting recognition and expanded OCR design

**Status:** Approved bounded engineering design for the next Issue #236 implementation sequence  
**Date:** 10 September 2026  
**Applies after:** SalCAPA v3.108  
**Parent requirement:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)

## Decision

SalCAPA will add handwriting recognition and difficult-document optical character recognition as native, source-grounded review capabilities. They will extend the established immutable-source, page/region lineage, processor-profile, tenant, sensitivity, disclosure, human-review, correction, audit, backup, recovery, and governed-link contracts. They will not create a parallel document system or a separate source of authority.

The implementation sequence will support:

1. bounded local recognition of printed, handwritten, and mixed text in authorized JPEG and PNG sources;
2. isolated page rendering and recognition for image-only or mixed-content PDF pages after the existing embedded-text path has been inspected;
3. exact page, image, line, word, and region linkage to the immutable source;
4. explicit uncertain, illegible, omitted, conflicting, and alternate readings rather than silent completion or correction;
5. independent human comparison with the source and append-only correction history;
6. server-controlled language, script, processor, model, vocabulary, resource, and cost profiles;
7. a separately enabled external document-recognition path when an approved provider materially improves format or recognition support and every governance gate is satisfied; and
8. manual transcription and region review whenever processing is unavailable, inappropriate, unauthorized, or outside a cost or sensitivity boundary.

Prepared text remains **Derived — Unverified** and **Awaiting Human Review**. Recognition does not establish authorship, authenticity, identity, intent, credibility, chronology, source truth, evidence, qualified intelligence, an assessment finding, a threat judgment, a plan requirement, an operational decision, or disclosure authority.

Map and plan interpretation, engineering conclusions, signature verification, forensic handwriting comparison, and facial or biometric functions remain separately bounded Issue #236 increments. Text recognition may recover visible labels or annotations from maps and plans, but it cannot interpret the map, establish geometry, or infer a facility condition by itself.

## Human and operational purpose

Field notes, forms, whiteboards, labels, logs, scans, photographs, marginal annotations, and historical records often contain useful information that is difficult to search or reuse. SalCAPA may prepare a reviewable transcription so Salus investigators, analysts, assessors, and planners can find the relevant source passage more efficiently. People remain responsible for deciding what the source says, what it means, whether it is reliable, and whether it may be used or disclosed.

The normal lifecycle is:

Authorized source and purpose → existing-text inspection → bounded page or image preparation → local recognition or separately authorized external recognition → unverified source-linked text alternatives → independent source comparison → confirm representation, correct, reject, or request more information → optional governed reference proposal → destination authority review

The interface will lead with familiar tasks such as **Extract Printed Text**, **Review Handwriting**, **Compare with Original**, **Correct Transcription**, and **Prepare Reference**. Technical processor, model, transform, provider, transmission, and hash details remain available through provenance details. SalCAPA must not imply that a person read, reviewed, verified, approved, or decided something when only a processing service prepared a suggestion.

## Capability boundaries

### Sources and page selection

The first implementation accepts only sources already governed by SalCAPA:

- single-frame JPEG and PNG images;
- PDF files that have passed the existing signature, structure, encryption, active-content, embedded-file, size, and integrity checks; and
- a full image, one PDF page, or a bounded rectangular source region selected for an authorized purpose.

For a PDF, SalCAPA first inspects the existing embedded-text derivative and page structure. It renders only the specifically authorized page or bounded page range when embedded text is absent, materially incomplete, or does not represent the visible text needed for the stated purpose. It does not OCR every PDF merely because OCR is available.

Scanned-PDF rendering occurs in a fixed isolated worker. Forms, signatures, scripts, actions, annotations with executable behavior, attachments, multimedia, remote references, hidden layers, and external resources are not executed or retrieved. The renderer records its exact binary, build, configuration, page box, rotation, resolution, color handling, and output hash. Rendered page bytes are ephemeral unless a separately governed derivative-retention requirement is approved.

The bounded implementation does not accept remote URLs, live camera feeds, video frames, animated images, multipage image containers, RAW camera formats, password-protected material, damaged files that require repair, or arbitrary client-supplied decoder options. These are sequencing or safety boundaries, not evidence that the source is unimportant.

### Recognition modes

A server-controlled profile may enable one or more of these modes:

- **Printed text:** difficult layouts, low contrast, rotated text, photographed pages, labels, and forms;
- **Handwritten text:** cursive or printed handwriting within the profile's validated language and script boundaries;
- **Mixed text:** source regions containing both printed and handwritten text, with the origin of each proposed segment preserved when the processor supports it;
- **Layout-aware text:** bounded reading order, lines, tables, form fields, check boxes, and key-value associations when the profile has validation evidence for those structures; and
- **Targeted region review:** recognition limited to a person-selected source region, such as a note, label, log entry, or annotation.

A profile cannot claim a capability that its exact model, language, script, source type, and validation evidence do not support. Unsupported scripts, languages, marks, layouts, or source conditions remain explicit information gaps. The first local implementation may begin with English and Latin-script material, but the record model and profile contract must support additional approved languages and scripts without changing historical derivatives.

The client may state the legitimate purpose and select an authorized source region. It cannot supply an executable, model, prompt, provider endpoint, credential, hidden initial text, language pack, dictionary, threshold, correction rule, retention rule, or disclosure audience.

### Prohibited handwriting conclusions

Ordinary handwriting recognition transcribes visible marks. It must not perform writer identification, signature verification, authorship attribution, personality analysis, health inference, impairment inference, demographic inference, deception or credibility assessment, intent analysis, or forensic document examination.

A similarity between handwriting samples cannot silently become a person relationship, an identity conclusion, corroboration, common authorship, or evidence. Any future forensic handwriting or signature-comparison capability requires its own lawful-purpose, qualification, validation, sensitivity, retention, disclosure, and human-authority design.

### Difficult text and uncertainty

Recognition must preserve what the source can and cannot support. It will not silently:

- spell-correct names, identifiers, addresses, dates, times, quantities, acronyms, or technical terms;
- complete cut-off, erased, obscured, crossed-out, overwritten, faint, or illegible text;
- resolve ambiguous characters such as zero/O, one/I/l, five/S, or punctuation without showing uncertainty;
- turn a numeric date into a specific day-month-year interpretation when the source is ambiguous;
- convert a 12-hour time to 24-hour time when AM/PM or context is missing;
- infer reading order, field association, checkbox state, table structure, or paragraph boundaries beyond the processor's supported evidence;
- translate, summarize, classify, or infer meaning from recognized words; or
- combine text from separate pages or regions into one continuous statement without explicit source mapping.

Where supported, the processor returns line and word polygons, alternate readings, recognition scores with documented semantics, script/language support facts, and quality limitations. SalCAPA presents understandable states such as **Clear Candidate Text**, **Uncertain Reading**, **Illegible Segment**, **Layout Needs Review**, and **Language Not Supported**. A processor score is not displayed as truth probability, source reliability, evidentiary weight, intelligence confidence, or analyst confidence.

## Native record model

### Recognition job

Each request creates an immutable job record containing:

- tenant, source material identifier, source version, source media type, and source SHA-256;
- legitimate purpose, requesting actor and role, request time, and source sensitivity;
- image, PDF page, page range, or selected source-region coordinates;
- embedded-text inspection result and the reason rendering or additional recognition was appropriate;
- renderer and recognition processor profiles with exact immutable snapshots;
- renderer, runtime, dependencies, language data, model artifacts, configuration, vocabulary, and license identifiers and hashes;
- page box, rotation, resolution, crop, resize, deskew, dewarp, denoise, contrast, binarization, color, and coordinate-remapping transforms;
- worker entry points, isolation limits, start and completion times, outcome, and bounded error code;
- measured duration, CPU time, peak memory and temporary storage where available;
- output page, region, line, word, character, and byte counts, including truncation or suppression facts;
- local or external processing route and the policy decision that authorized that route;
- attributable processing cost evidence without automatic customer charging; and
- lifecycle, retention, legal-hold, disclosure, correction, supersession, and audit linkage.

A retry creates a new linked job. A failed, expired, suspended, mismatched, or unauthorized profile cannot be edited into success.

### Recognition segment

Each proposed text segment is separate from the source and from person-entered transcription. It contains:

- immutable job, source, page, region, processor, model, configuration, vocabulary, renderer, transform, and route lineage;
- stable segment identifier and reading order proposed by the processor;
- exact source polygon or bounding region remapped to the original image or PDF page;
- prepared text exactly as returned after schema validation;
- printed, handwritten, mixed, mark, checkbox, table, field, or unknown segment type when supported;
- alternate readings and uncertain character or word spans;
- score and score semantics only when responsibly defined by the approved profile;
- quality, language, script, orientation, occlusion, clipping, strike-through, overwriting, background, compression, and layout limitations when supported;
- initial state **Awaiting Human Review**;
- tenant, sensitivity, purpose, retention, and disclosure posture; and
- immutable original output plus append-only review, correction, contradiction, rejection, and supersession history.

Processor output remains data. It cannot contain executable instructions, initiate tools, request research, select another provider, activate monitoring, create relationships, alter a plan, approve a disclosure, change commercial scope, or modify authority.

### Human review and correction

The requester cannot independently complete the review of the same derivative. An authorized reviewer compares each relevant segment with the original source and records one of:

- **Confirm Representation:** the proposed characters and source region reasonably represent the visible marks;
- **Correct:** the reviewer records corrected text, region, reading order, segment type, or limitations while preserving the original output;
- **Reject:** the prepared text does not reasonably represent the source or is unsuitable for the stated purpose; or
- **Needs More Information:** the source, language, layout, context, authority, or reviewer qualification is insufficient.

Review confirms representation only. It does not validate source truth, authenticity, authorship, chronology, reliability, meaning, identity, evidentiary status, or disclosure authority. A reviewer may mark a passage **Illegible** without being forced to guess.

Batch review is permitted only when each selected segment, page, source region, text, uncertainty, and proposed outcome remains individually visible and attributable. There is no opaque **accept all** action. Corrections and later improvements create append-only records and never overwrite the prepared output or immutable source.

### Governed downstream use

Only reviewed or corrected text may be proposed for governed use in SalINTEL, Personnel Assessment, Facility Assessment, SalTHIRA, SalOPS, Mission Map, PROVE, Strategic Horizon Monitoring, reports, or an authorized Protected Member view.

The proposal retains the exact reviewed text, source region, uncertainty, destination, purpose, initiator, disclosure posture, and required destination authority. Destination acceptance applies that domain's rules. It does not silently establish a person or organization identity, allegation, observation, indicator, concern, hypothesis, inference, qualified finding, threat judgment, assessment result, plan requirement, priority, task, monitoring scope, cost, price, customer charge, or release approval.

Search results must return the user to the exact source page or image region and show review state. Rejected text is not searchable. Unreviewed text may be indexed only in a restricted review queue when tenant, role, sensitivity, purpose, and policy permit it; it cannot appear as ordinary authoritative content.

## Local processing profile and supply chain

The local path is request driven and uses deployment-supplied, hash-verified artifacts. The application does not download models, language data, dictionaries, runtimes, renderers, or packages during request handling.

An enabled local profile specifies:

- approved source types, purposes, tenants or service contexts, sensitivity ceiling, language, and script;
- printed, handwritten, mixed, layout, table, form, checkbox, and region capabilities that are actually validated;
- renderer, recognition runtime, model, language data, dictionaries, configuration, and vocabulary with exact versions, paths, hashes, provenance, license, and approved use;
- preprocessing, rendering, coordinate, reading-order, text-normalization, and output-decoding contracts;
- category- or field-specific validation evidence, known limitations, and misuse boundaries;
- source-size, page-count, page-range, pixel, resolution, region, duration, memory, CPU, temporary-storage, output, and concurrency ceilings;
- score interpretation, uncertainty thresholds, alternate-output rules, truncation, and suppression behavior;
- quality, accessibility, language, bias, privacy, records, security, procurement, and legal review evidence;
- effective date, expiration, approver, suspension, supersession, and rollback state;
- no-network boundary and external-processing flag fixed to false; and
- per-job and period resource or cost ceilings.

Missing, writable, unexpected, expired, suspended, tampered, or hash-mismatched artifacts fail closed. SalCAPA remains usable through the original source, existing embedded text, and manual transcription.

## External document-recognition route

An external OCR or document-intelligence service is a separately enabled route within the same native record model. It is not an automatic fallback. Local failure, poor quality, unsupported handwriting, or user preference does not authorize transmission.

Before any external job, SalCAPA must verify a server-controlled provider profile containing:

- approved provider, service, API version, capability, deployment, endpoint, and geographic processing region;
- contractual and data-processing terms, confidentiality posture, permitted data classes, subprocessors, retention, abuse monitoring, logging, model-training use, human access, deletion, and incident-notification terms;
- approved tenant, purpose, role, source type, sensitivity ceiling, jurisdiction, disclosure posture, and data-residency rules;
- source minimization and whether a page or region can be sent instead of the complete document;
- private networking or allowlisted egress, certificate and endpoint validation, workload identity or secret reference, and credential rotation;
- request and response size, page, duration, rate, concurrency, per-job spend, period spend, and circuit-breaker ceilings;
- provider output schema, score semantics, language and handwriting support, known limitations, and validation evidence;
- effective date, expiration, approver, suspension, rollback, provider-change, and emergency-disable controls; and
- the disclosure users receive before requesting processing and the authority required to proceed.

Credentials remain in the approved secret store and are never persisted in source records, jobs, logs, URLs, client state, exports, or the repository. The browser never calls a provider directly.

Each external job records an auditable transmission manifest:

- exact source, page, region, and transmitted-byte hashes;
- minimization and redaction decisions;
- requesting actor, purpose, policy decision, provider profile, and approval basis;
- provider, service, API version, deployment, endpoint identity, and region;
- transmit, provider-response, receipt, and deletion-request times;
- response hash, provider request identifier when safe, result disposition, and bounded error;
- retention, logging, training-use, and terms versions in force;
- measured or invoiced cost when available; and
- confirmation that no automatic disclosure, billing, or downstream authority followed.

External responses remain **Derived — Unverified**, receive the same independent source-comparison requirement, and are visibly distinguishable in provenance details. An approved external route may be materially useful and is therefore part of the intended capability, but it remains disabled unless the deployment supplies a complete approved provider profile and current authorization.

## Worker isolation and failure behavior

Local rendering and recognition run outside the web process through fixed executable paths without a shell. Workers receive read-only verified source bytes and a bounded manifest. They have a minimal environment, private temporary directory, no database credentials, no application token, no tenant-wide access, and no authority to write application records or perform follow-on actions.

The orchestrator enforces:

- tenant, role, purpose, source lifecycle, sensitivity, disclosure, retention, legal-hold, and cost eligibility;
- source signature, media type, hash, page structure, page count, dimensions, pixels, region, and file-size limits;
- renderer, runtime, dependency, model, language-data, configuration, and vocabulary hash verification;
- fixed rendering and recognition arguments, schemas, protocol restrictions, and output encodings;
- page, region, transform, polygon, reading-order, language, score, character, and output bounds;
- subprocess wall-time, CPU, memory, file, temporary-storage, open-file, process, and output ceilings;
- maximum pages, segments, lines, words, alternatives, and characters per job;
- no network for local workers and allowlisted policy-controlled egress only for an explicitly external job; and
- transactional creation of a completed job and derivative set only after complete validation.

Timeout, memory exhaustion, decoder failure, renderer failure, malformed output, non-finite score, invalid polygon, unsupported language, excessive output, artifact mismatch, worker crash, provider error, provider-policy mismatch, data-region mismatch, spend-ceiling failure, or audit-manifest failure creates no partial searchable derivative. Temporary page images and request payloads are removed after success or failure unless a governed retention rule explicitly requires preservation.

Logs, metrics, traces, notifications, URLs, analytics, and crash reports exclude source text, page images, exact source regions, names, identifiers, handwriting samples, Protected Member content, credentials, provider payloads, and sensitive metadata. Bounded technical failure codes remain available for support and audit.

## Privacy, sensitivity, disclosure, and trust

A transcription inherits the source tenant and at least the source sensitivity. Handwriting, signatures, personal notes, health information, personnel material, legal material, investigation content, facility information, and identifiers may require a higher sensitivity based on purpose and content. Recognition can make information substantially easier to find and disclose, so access to the source does not automatically grant broad access to the searchable derivative.

Protected Member views show only explicitly released reviewed text. They do not expose Salus-internal reasoning, hidden regions, processor diagnostics, provider configuration, another member's information, unreviewed alternatives, or internal audit evidence. Cross-tenant recognition, comparison, shared learning, and unauthorized cross-member search fail closed.

Source material and derivatives are not used to train, fine-tune, adapt, or evaluate a shared model unless a separate explicit lawful agreement and approved model-governance process exists. No such shared-training path is introduced by this design.

Retention, legal hold, correction, supersession, and deletion eligibility apply independently to the source, rendered-page facts, job, segment, review, correction, transmission manifest, governed reference, and approved disclosure. Deleting an eligible derivative does not rewrite immutable approved records or required audit evidence.

The interface explains the purpose, source basis, processing route, uncertainty, reviewer, authority, disclosure boundary, and next step. It avoids blame and false precision. Absence of recognized text means only that the configured process returned no bounded proposal; it does not prove that no text is present.

## Azure and cost posture

The initial local capability uses bounded, request-driven CPU processing within the established deployment posture. It adds no standing GPU, always-on worker tier, open public endpoint, automatic scale-out, or automatic purchase of an Azure or third-party recognition service.

Concurrency defaults to one bounded recognition job per application instance. Server-controlled ceilings protect CPU, memory, temporary storage, page volume, and approved spend. Capacity exhaustion returns understandable manual and retry options; it does not weaken limits or provision additional services.

The external route may use an approved Azure or other document-recognition provider only after the provider profile, data handling, region, identity, networking, retention, security, procurement, legal, privacy, validation, and cost controls are supplied and enabled. Per-job and period ceilings fail closed. Cost evidence feeds internal commercial review but never automatically changes scope, package, price, invoice, or customer charge.

## Required implementation evidence

Before freezing an implementation release, the candidate must prove:

- deterministic reconstruction of every renderer, recognition runtime, dependency, model, language artifact, configuration, and vocabulary used locally;
- immutable original-byte and source-hash preservation before and after every success and failure;
- correct handling of fictional demonstration printed, handwritten, mixed, faint, rotated, crossed-out, overwritten, low-contrast, form, table, checkbox, photographed-page, image-only PDF, and mixed-content PDF fixtures;
- exact source-to-page-to-render-to-region-to-segment coordinate and hash lineage;
- embedded-text inspection before PDF rendering and no indiscriminate OCR of every PDF;
- uncertainty, illegible passages, alternate readings, unsupported language, ambiguous date/time, and reading-order limitations without silent correction;
- no authorship, signature, identity, personality, health, demographic, credibility, intent, evidence, or threat conclusions;
- independent source comparison, append-only correction, rejection, contradiction, and supersession without overwriting source or processor output;
- restricted search behavior and source-linked results showing review state;
- server control of executable, model, language, configuration, dictionary, provider, endpoint, credential, thresholds, limits, route, cost, retention, and disclosure;
- local no-network execution and external transmission only through an explicitly enabled provider profile;
- complete external transmission manifest, source minimization, region enforcement, credential protection, retention posture, response hashing, and spend controls;
- no automatic external fallback, provider switching, translation, summarization, relationship creation, monitoring, disclosure, billing, or downstream authority;
- tenant, cross-member, role, sensitivity, purpose, jurisdiction, retention, legal-hold, and Protected Member denial paths;
- bounded malformed, encrypted, active-content, remote-reference, excessive-page, excessive-pixel, excessive-output, timeout, memory, storage, renderer, worker, provider, policy, cost, and artifact-mismatch failures with no partial derivative;
- temporary page and request-payload cleanup after success and failure;
- manual transcription and original-source review when any processing route is unavailable;
- portable backup verification and disaster-recovery validation for jobs, segments, reviews, corrections, manifests, and governed references;
- SQLite and PostgreSQL 16 behavior;
- production-container execution under the unprivileged identity;
- measured image-size, cold-start, CPU, memory, temporary-storage, throughput, concurrency, and optional provider-cost behavior;
- dependency audit, Bandit, repository hygiene, Azure policy/infrastructure validation, CodeQL, and deterministic reconstruction; and
- every existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, emergency-planning, visual, date/time, accessibility, and frozen-release regression.

Fixtures must be fictional demonstration material created for validation. No confidential, personal, Protected Member, investigation, customer, employee, real signature, or licensed third-party handwriting sample may be committed to the repository.

## Implementation sequence

The approved implementation sequence is:

1. add the native recognition job, segment, review, correction, profile, and recovery contracts;
2. add isolated JPEG/PNG local printed, handwritten, mixed, and targeted-region recognition behind deployment-supplied hash-verified artifacts;
3. add bounded scanned-PDF page rendering after embedded-text inspection;
4. add the separately enabled external-provider route and auditable transmission manifest;
5. complete an integrated fictional analyst journey, accessibility review, recovery exercise, and all required gates; and
6. freeze only after the exact candidate commit is green across every required validation family.

A deployment may enable only the capabilities for which it has approved artifacts and profiles. Local or external unavailability never prevents authorized people from reviewing the immutable source or recording a manual transcription.

## Deferred sequence

After this handwriting and expanded-OCR implementation is accepted, Issue #236 proceeds to native map, plan, diagram, and facility-image interpretation. The separately governed facial and biometric module follows its own lawful-purpose, sensitivity, privacy, validation, identity, retention, disclosure, and human-authority design.

Additional languages, scripts, document formats, specialized handwriting models, advanced table/form reconstruction, signature or forensic-document work, and broader provider capabilities require separately approved profiles and validation. They are not permanent exclusions, but they do not silently inherit authority from this bounded design.

## Product principle

**Preserve the source. Prepare the text that is actually supported. Show the exact page and marks behind it. Keep uncertainty visible. Let authorized people review, correct, and decide how it may be used.**
