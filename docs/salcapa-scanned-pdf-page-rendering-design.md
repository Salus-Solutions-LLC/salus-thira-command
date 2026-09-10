# SalCAPA scanned-PDF page rendering design

**Status:** Approved bounded engineering design candidate for Issue #236  
**Date:** 10 September 2026  
**Applies after:** SalCAPA v3.109  
**Parent requirement:** [Issue #236](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/236)

## Decision

SalCAPA will add isolated, request-driven rendering of specifically authorized PDF pages when the existing strict embedded-text inspection shows that visible text is absent, materially incomplete, or unsuitable for the stated review purpose. The rendered page is an intermediate representation of the immutable governed PDF, not a new source of truth. It may be passed to the approved local printed, handwriting, mixed-text, or targeted-region recognition path introduced in v3.109.

This increment will be native to the existing material, PDF, and handwriting-recognition architecture. It will not create a parallel document store, silently process every PDF, transmit material externally, execute PDF behavior, infer meaning, or establish a finding, authority, decision, disclosure, or charge.

The normal lifecycle is:

Governed PDF → strict signature, structure, integrity, encryption, active-content, embedded-file, page-count, and embedded-text inspection → identify the exact page and reason additional review is needed → authorized person requests **Review Scanned Page** → isolated page rendering → hash and coordinate validation → approved local recognition → **Derived — Unverified** page-linked text → independent comparison with the original PDF → confirm, correct, reject, or request more information → optional governed destination proposal

## Human and operational purpose

Scanned reports, handwritten forms, historical records, marginal notes, image-only plans, and mixed PDFs often contain visible information that has no dependable embedded-text layer. SalCAPA may prepare a source-linked page image and candidate transcription so investigators, analysts, assessors, and planners can review that information without re-keying the entire document.

People remain responsible for deciding what the page shows, what the visible marks say, what the information means, whether it is reliable, and whether it may support intelligence, assessment, planning, operations, assurance, or disclosure. The interface will lead with familiar actions:

- **Inspect Existing Text**
- **Select Pages for Review**
- **Review Scanned Page**
- **Compare With Original**
- **Correct Transcription**
- **Prepare Reference**

Before rendering, the user sees the stated purpose, selected pages, source sensitivity, processing route, resource boundary, retention posture, reviewer requirement, and what happens next. The interface never implies that a person reviewed or verified a page when only the rendering and recognition workers ran.

## Eligibility and sequencing boundary

Only an active PDF already preserved as a governed SalCAPA material may enter this path. The PDF must pass the existing strict PDF controls without repair or weakening:

- PDF header and recorded media type agree;
- source bytes match the immutable source SHA-256;
- source size and page count remain within the server profile;
- the file is not encrypted or password protected;
- no rejected document action, page action, executable behavior, rich media, form behavior, embedded file, portfolio, or external resource is present; and
- strict parsing and decoded-content inspection complete within the resource boundary.

SalCAPA first records the existing embedded-text inspection for every requested page. Rendering is permitted only when one of these page-specific reasons is recorded:

- **No Embedded Text** — the page has no usable embedded-text representation;
- **Visible Text Missing** — visible text needed for the stated purpose is absent from the extracted representation;
- **Embedded Text Mismatch** — the extracted order or characters materially differ from the visible page;
- **Handwriting or Mark Review** — handwriting, check marks, annotations, labels, or other visible marks require source comparison; or
- **Layout Review Needed** — the visible relationship among fields, rows, columns, labels, or regions cannot be reviewed from the embedded text alone.

The user may select a single page, an inclusive bounded page range, or bounded regions on selected pages. The first implementation does not silently render an entire PDF because one page lacks text. Batch selection remains individually attributable by page and is limited by the active server-controlled profile.

Remote URLs, password entry, damaged-file repair, arbitrary client renderer options, live documents, embedded attachments, multimedia, external resources, and automatic fallback to another provider are prohibited in this increment.

## Rendering profile and low-cost deployment posture

Rendering uses a fixed local worker outside the web process. The deployment supplies an approved renderer and immutable profile; request handling never downloads a renderer, font pack, model, language data, dependency, or configuration.

The approved profile records:

- renderer executable, runtime, dependency, font-data, color-profile, and configuration versions and hashes;
- provenance, license, approved use, validation evidence, known limitations, effective date, expiration, approver, suspension, supersession, and rollback state;
- accepted PDF versions and page-box, rotation, transparency, image, font, and color behaviors;
- fixed resolution, color mode, antialiasing, background, crop, scaling, and output encoding;
- source, page, selected-range, page-pixel, aggregate-pixel, memory, CPU, wall-time, temporary-storage, output-byte, and concurrency limits;
- tenant, role, purpose, source type, sensitivity ceiling, disclosure posture, and cost eligibility;
- no-network enforcement and an external-processing flag fixed to false; and
- per-job and period resource ceilings with attributable internal cost evidence.

The initial profile should use CPU-capable rendering, one request-driven worker at a time, and no standing GPU, queue, duplicate permanent source store, public endpoint, paid external document service, or automatic scale-out. Suggested initial validation ceilings are no more than 12 selected pages per job, 300 DPI, 40 million output pixels per page, 120 million aggregate pixels, 90 seconds wall time, 512 MiB address space, and 512 MiB private temporary storage. These are server-controlled engineering defaults, not client promises, and may change prospectively only through an approved, tested profile version.

Missing, writable, expired, suspended, unexpected, tampered, or hash-mismatched renderer artifacts fail closed. The original PDF, embedded-text representation, and manual page review remain available.

## Isolation and safe rendering

The orchestrator writes verified source bytes into a private temporary directory with restrictive permissions and starts the fixed worker without a shell. The worker receives only a bounded manifest and read-only source path. It receives no database credential, application token, tenant-wide storage access, provider credential, or outbound network access.

The worker must not execute or retrieve scripts, actions, forms, annotations with behavior, attachments, multimedia, links, remote fonts, remote images, external color profiles, or other network resources. It cannot repair the PDF, ignore structural errors, request a password, invoke tools, select another page, expand the page range, initiate recognition, or write application records.

The orchestrator validates the complete response before creating successful records. Invalid output, unexpected files, renderer mismatch, source-hash mismatch, page mismatch, invalid dimensions, invalid rotation, non-finite geometry, pixel overflow, output overflow, timeout, memory exhaustion, worker crash, policy denial, or cost-ceiling failure creates no partial successful page set or recognition segment. A bounded failed-job record may retain technical facts without client content, page pixels, exact geographic coordinates, secrets, or unsafe error detail in logs.

Temporary rendered bytes are removed after validated recognition or authorized viewing unless a separate derivative-retention purpose is approved. Deletion of temporary bytes does not delete the source PDF, render facts, hashes, recognition lineage, review, correction, or audit record required by policy.

## Native record model

### PDF page-render job

Each request creates an immutable job record containing:

- tenant, source material identifier, source version, source SHA-256, and source sensitivity;
- legitimate purpose, requester and role, request time, selected page or range, and any selected source regions;
- strict PDF inspection job and embedded-text derivative identifiers and hashes;
- the embedded-text availability fact and rendering reason for each selected page;
- renderer profile and exact profile snapshot, executable/runtime/dependency/font/configuration identifiers and hashes;
- page boxes, document rotation, requested resolution, color mode, output encoding, and every crop, scale, rotation, padding, or coordinate transform;
- worker isolation limits, start and completion time, outcome, and bounded failure code;
- measured duration, CPU time, peak memory, temporary storage, page count, pixels, and output bytes where available;
- external-processing flag fixed to false and attributable cost evidence without automatic customer billing;
- retention, legal hold, disclosure, correction, supersession, and audit linkage.

A retry creates a new linked job. A failed job cannot be edited into success.

### Rendered-page fact

For every successfully validated page, SalCAPA records:

- render-job identifier, source material identifier and hash, one-based PDF page number, and source page label when present;
- media box and crop box in PDF points, inherited and effective rotation, user unit, and coordinate origin;
- rendered width and height in pixels, resolution, color mode, output format, and rendered-byte SHA-256;
- exact forward and inverse transforms between PDF page coordinates and rendered-image coordinates;
- clipping, transparency, font substitution, missing-glyph, image-resolution, color, or other renderer limitations when available;
- ephemeral or retained-byte posture and any retained governed derivative identifier;
- source sensitivity, purpose, disclosure posture, retention, and legal-hold state.

The page image is **Rendered Representation — Not Source Truth**. Its hash proves which rendered bytes were used; it does not prove that the PDF is authentic, accurate, current, complete, or reliable.

### Recognition linkage

The v3.109 recognition job and segment model will be extended so a PDF-page job records the render job and rendered-page fact. Every candidate segment retains:

- the immutable PDF source and SHA-256;
- exact one-based PDF page number and source page label;
- rendered-page SHA-256 and renderer-profile lineage;
- page-space polygon or bounding region in PDF points;
- corresponding rendered-image pixel region;
- the complete forward and inverse coordinate transform;
- recognition processor, model, language data, configuration, vocabulary, route, uncertainty, alternatives, and limitations; and
- independent review and append-only correction history.

Coordinates are valuable evidence. SalCAPA preserves exact page coordinates and all authorized geographic coordinates rather than discarding or unnecessarily coarsening them. Authorized users may search, map, correlate, analyze, report, and export geographic coordinates when the governed purpose and disclosure authority permit it. Controls prevent unintended exposure through unnecessary application logs, generic notifications, URLs, metrics, crash reports, unauthorized search, or unauthorized exports.

## Uncertainty, human review, and correction

Rendering does not cure ambiguity. Rotation, crop boxes, skew, compression, low resolution, faint marks, bleed-through, overlays, transparency, font substitution, missing glyphs, hidden text, and stale OCR layers may produce contradictions between embedded text, rendered pixels, and recognition output.

SalCAPA preserves those contradictions. It does not silently prefer the embedded layer, rendered page, processor output, or person-entered transcription. The reviewer compares the candidate segment with the original PDF page and records:

- **Confirm Representation**
- **Correct**
- **Reject**
- **Needs More Information**

The requester cannot independently complete review of the same derivative. Confirming representation addresses visible characters and region mapping only. It does not establish source truth, authorship, signature validity, identity, chronology, intent, credibility, evidentiary status, intelligence, a finding, a risk priority, a plan requirement, an operational decision, or disclosure authority.

Original embedded text, renderer output hashes, recognition output, uncertainty, and corrected text remain distinct and append-only. A reviewer may mark a passage **Illegible** or **Layout Needs Review** without guessing.

## Search, downstream use, and disclosure

Only independently reviewed or corrected text may be proposed for ordinary governed search or destination use. Search returns the user to the exact PDF page and source region and displays the review state. Rejected text is not searchable. Unreviewed text may appear only in a restricted review queue when tenant, role, sensitivity, and purpose permit it.

Reviewed text may be proposed to SalINTEL, Personnel Assessment, Facility Assessment, SalTHIRA, SalOPS, Mission Map, PROVE, Strategic Horizon Monitoring, reports, or an authorized Protected Member view. Destination acceptance applies that domain's authority and disclosure rules. It does not silently establish an observation, allegation, indicator, concern, hypothesis, inference, qualified finding, threat judgment, assessment result, priority, plan requirement, task, monitoring scope, price, customer charge, or release approval.

Protected Member views expose only explicitly released material for that member. They never expose another member's source, page image, text, coordinates, Salus-internal reasoning, processor configuration, hidden review queue, or audit evidence.

## Backup, recovery, and graceful degradation

Portable backup and recovery preserve source identifiers and hashes; embedded-text inspection; render jobs and page facts; exact renderer profiles and transforms; recognition jobs and segments; original prepared text; human reviews and corrections; sensitivity, retention, legal-hold, disclosure, and audit evidence; and governed destination proposals.

Recovery validates relationships and hashes without silently re-rendering or re-running recognition. Historical records remain reviewable even if the active renderer or recognition profile has changed or is unavailable. Missing current artifacts do not rewrite historical provenance.

When rendering is unavailable, unauthorized, degraded, outside the resource boundary, or too costly, SalCAPA presents the original PDF, existing embedded text, and a clear manual page-review or transcription path. Local failure never authorizes external transmission.

## Required implementation evidence

Before a release candidate may freeze, validation must prove:

- embedded-text inspection always precedes rendering and records a page-specific reason;
- only explicitly selected pages or bounded ranges render;
- source bytes and SHA-256 remain unchanged before and after rendering;
- encrypted, active, embedded-file, malformed, repaired, mismatched, oversized, excessive-page, and unsupported PDFs fail closed;
- renderer executable, runtime, dependency, font, color, and configuration hashes are verified;
- fixed no-shell, no-network, least-privilege subprocess isolation works in the production container;
- page boxes, rotation, resolution, pixel dimensions, page labels, output hashes, and forward/inverse transforms are exact and bounded;
- PDF point regions round-trip to rendered pixels and back within a documented tolerance;
- selected-page, page-pixel, aggregate-pixel, output-byte, time, memory, temporary-storage, and concurrency limits fail closed;
- malformed renderer output, unexpected files, invalid geometry, non-finite values, page mismatch, output overflow, timeout, resource termination, and tampered artifacts create no partial successful records;
- rendered bytes are ephemeral by default and private temporary material is removed after use;
- PDF render facts link immutably to v3.109 recognition jobs, segments, uncertainty, alternatives, and reviews;
- results begin **Derived — Unverified** and **Awaiting Human Review**;
- independent review and append-only correction preserve source, embedded text, rendered hash, and original processor output;
- no automatic authorship, signature, identity, authenticity, chronology, intent, credibility, evidence, intelligence, finding, threat, priority, plan, task, monitoring, disclosure, billing, or release conclusion occurs;
- exact page and authorized geographic coordinates are preserved and usable while unintended disclosure paths remain controlled;
- tenant, role, sensitivity, purpose, source lifecycle, Protected Member, cross-member, retention, legal-hold, disclosure, suspension, and cost boundaries fail closed;
- portable backup, restore, hash, relationship, and historical-profile validation pass without silent reprocessing;
- original-PDF, embedded-text, and manual-review capability remain available during graceful degradation;
- no confidential, personal, Protected Member, investigation, or licensed third-party content is committed; and
- fresh SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, reconstruction, repository-hygiene, Azure-policy/infrastructure, CodeQL, recovery, and every existing regression gate pass on the exact candidate.

The controlled validation pull request must be closed without merge. `main`, `development/v1.17`, `release/v1.16`, v3.109, and every earlier frozen release remain unchanged.

## Sequenced follow-on increments

After the bounded local scanned-PDF path is implemented and validated, Issue #236 continues through separately governed decisions for:

1. additional approved local OCR languages, scripts, layout, table, form, and checkbox profiles;
2. an optional external document-recognition route with provider, privacy, residency, retention, identity, network, transmission, validation, and spend controls;
3. maps, plans, diagrams, facilities, routes, proximity, and geographic relationships;
4. specialized damage, equipment, protective-control, and facility-condition profiles;
5. separately approved facial and biometric presence, quality, and authorized-reference comparison; and
6. additional image formats, video frames, advanced visual relationships, and performance scaling.

## Product principle

**Inspect before rendering. Render only what the authorized review requires. Preserve exact source and coordinate lineage. Let Salus people decide what the information means and what happens next.**
