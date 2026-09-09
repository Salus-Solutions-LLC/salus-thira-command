# SalCAPA safe PDF extraction design

**Status:** Approved engineering design for the next bounded Issue #131 increment  
**Date:** 09 September 2026  
**Applies after:** SalCAPA v3.102  
**Parent requirements:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128)

## Decision

The next processing increment will add a local, request-driven worker for text-bearing PDF source material. It will reuse the v3.102 immutable-source, derivative, lineage, review, search, access-control, audit, backup, and recovery contracts.

The worker is deliberately limited to embedded text and basic page structure. It is not an OCR, image-analysis, form-processing, signature-validation, document-repair, PDF-rendering, attachment-extraction, or general document-conversion service.

The implementation candidate will use an exactly pinned, dependency-audited release of the pure-Python pypdf library in an isolated child process. The approved design is based on pypdf 6.18.0, released 07 September 2026. The version must be rechecked at implementation time and changed only through the normal dependency and validation gates. Official documentation warns that PDF page content-stream parsing can require very large amounts of memory and that PDF files do not provide a dependable semantic layer; these limitations drive the resource-isolation and uncertainty controls below:

- [pypdf 6.18.0 package record](https://pypi.org/project/pypdf/)
- [pypdf text-extraction limitations](https://pypdf.readthedocs.io/en/stable/user/extract-text.html)
- [pypdf PdfReader contract](https://pypdf.readthedocs.io/en/stable/modules/PdfReader.html)

## Human and operational purpose

Salus personnel need to locate and review governed PDF records, including plans, reports, assessments, research, and historical commercial material, without first creating and uploading a separate text copy. The worker prepares a review aid. It does not decide what the source means, determine whether it is authentic or current, qualify intelligence, establish a finding, approve a plan, set a price, validate a cost, or authorize disclosure.

The user-facing lifecycle remains:

Original PDF → separate derived text representation → Awaiting Human Review → Human Reviewed or Rejected

Human review confirms whether the extracted representation is usable for source review. It does not certify the truth, completeness, authorship, custody, approval, legal effect, or current applicability of the PDF.

## Included material

The first PDF worker will accept only material that:

- has the .pdf extension and an approved PDF media type;
- begins with a supported PDF header and ends within a bounded source size;
- is not encrypted or password protected;
- can be opened in strict parsing mode without repair or recovery;
- remains within the page, object-recovery, time, memory, decoded-stream, and output limits;
- contains no declared embedded file, JavaScript, launch, remote-action, rich-media, XFA, or submission feature that requires rejection under this design.

For an accepted PDF, the worker may extract:

- the PDF header version;
- total page count;
- one page-delimited text section per source page;
- page index and source-stored page label when safely available;
- page rotation and page dimensions as source-stored processing facts;
- limited document-information metadata such as title, subject, author-as-recorded, creator, producer, keywords, creation time, and modification time.

Page boundaries must be explicit in the derivative. A blank or image-only page must remain represented as a page with no extracted embedded text rather than silently disappearing.

## Text and structure boundaries

PDF is a presentation format, not a dependable semantic document model. The worker must therefore:

- preserve source page order;
- identify extracted text order as an approximation;
- avoid claiming that apparent columns, tables, headers, footers, lists, paragraphs, reading order, or section hierarchy were reconstructed correctly;
- avoid table-to-row conversion in this increment;
- avoid image captions, diagram interpretation, map interpretation, handwriting recognition, and visual inference;
- avoid silently removing repeated headers, footers, page numbers, watermarks, hidden text, or background text;
- normalize only bounded control characters and line endings needed for safe storage and search;
- identify truncation at the document and page level;
- identify pages with little or no embedded text as **Text Not Available — OCR Review Needed**, without starting OCR.

A PDF may contain a hidden or previously OCR-produced text layer that differs from its visible page. The derivative must state that extracted text may include non-visible, out-of-order, duplicated, or stale text and requires comparison with the original PDF.

## Explicit exclusions

The first PDF worker will reject or defer:

- encrypted or password-protected PDFs, without accepting a password;
- malformed PDFs requiring repair, non-strict recovery, or speculative object reconstruction;
- PDFs over the approved source-size, page-count, processing-time, memory, object, decoded-stream, or output limits;
- embedded files and file specifications intended for extraction;
- JavaScript, document-level additional actions, launch actions, remote-go-to actions, URI actions, form submission, rich media, XFA, and other active or external behaviors;
- portfolio/package PDFs and ambiguous multi-document containers;
- incremental-update interpretation beyond the parser's accepted current object graph;
- attachment extraction;
- form-field data extraction;
- annotation, comment, layer, article-thread, outline, or bookmark extraction;
- digital-signature or certificate validation;
- PDF/A conformance claims;
- image extraction, rendering, OCR, handwriting recognition, facial or object analysis, map/geospatial interpretation, audio, and video;
- entity, person, threat, allegation, relationship, location, date, duplicate, price, or cost conclusions;
- semantic table, paragraph, heading, reading-order, or layout reconstruction.

Unsupported material remains immutable and available for authorized human review or a later compatible worker.

## Isolation and resource controls

PDF parsing will not run inside the web request process. The governed orchestration layer will start a fixed child-process entry point without a shell and with a minimal environment. The child process will:

- run under the existing unprivileged production-container identity;
- receive a read-only, mode-0600 temporary copy whose SHA-256 has already been verified against the governed source record;
- use a new empty working directory and write no persistent source or derivative file;
- import only the approved parser and standard-library modules needed for the worker;
- perform no database, network, disclosure, billing, authorization, rendering, or external-program action;
- receive fixed server-controlled limits rather than client-selected parser options;
- return one bounded machine-readable result through a pipe;
- be terminated on wall-time, CPU-time, address-space, file-size, open-file, subprocess, or output-limit breach;
- have its temporary directory removed after success or failure.

The initial implementation defaults will be conservative and server controlled:

- maximum stored source size: 64 MiB;
- maximum pages: 1,000;
- maximum extracted characters: 2,000,000;
- maximum aggregate decoded page-content bytes: 64 MiB;
- maximum decoded bytes considered for one page: 16 MiB;
- maximum wall time: 45 seconds;
- maximum CPU time: 30 seconds;
- maximum child-process address space: 512 MiB;
- maximum child-produced result: 16 MiB;
- strict PDF parsing enabled;
- parser root-object recovery bounded and non-strict recovery disabled.

The implementation may choose lower values when necessary to fit the existing low-cost Azure container. Raising any limit requires a reviewed code change and fresh gates; clients cannot override limits through the API.

Because decoding a malicious content stream can itself consume excessive memory, the child-process memory and time limits are authoritative even when the parser cannot safely estimate expanded content in advance. A resource-limit termination is a controlled processing failure, not a reason to retry automatically with weaker limits.

## Active-content and external-reference controls

The worker never executes PDF content. Before text extraction, it must inspect only bounded catalog and page references needed to identify disallowed declared features. A declared embedded-file, JavaScript, launch, remote, rich-media, XFA, or submission feature causes the first worker to fail closed.

The worker must not:

- evaluate JavaScript;
- activate actions or annotations;
- open or extract attachments;
- follow URI or remote-go-to targets;
- submit forms;
- resolve external streams;
- render a page;
- invoke Ghostscript, a browser, office software, image tools, shell commands, or another executable;
- fetch fonts, color profiles, images, linked content, or metadata from the network.

Internal page traversal needed to read the approved page tree is allowed. Links, actions, attachments, forms, and embedded media are not included in the derivative.

## Derived records and provenance

One successful job will create an **Extracted PDF Text** derivative using the existing transactional orchestration contract. The derivative must record:

- tenant and source material;
- exact source SHA-256;
- exact derivative SHA-256;
- processor name and exact version;
- extraction method and PDF header version;
- source page count and pages represented;
- creation date and time;
- document and page truncation facts;
- image-only or low-text page indicators;
- active-feature inspection result;
- uncertainty and limitation notes;
- review state and reviewer lineage.

Limited metadata may be included in the same derivative as a clearly separated **Source-stored PDF metadata** section. It is never independently verified. Metadata must not be treated as proof of identity, authorship, ownership, custody, authenticity, approval, signature validity, chronology, retention status, or recency.

Search results inherit the source tenant, role, and sensitivity restrictions. Rejected derivatives remain excluded from ordinary search. A later PDF version creates a new source record or governed version reference and a new derivative; it cannot rewrite a historical derivative or the source basis for an approved record.

## Failure behavior

No derivative is created unless the worker completes successfully and the orchestration layer validates:

- source hash equality;
- approved media type and extension;
- bounded machine-readable child output;
- expected parser name and version;
- page and output limits;
- derivative hash;
- tenant and source-record relationship.

A parse, encryption, active-feature, resource, malformed-output, integrity, or unsupported-format failure:

- leaves the original bytes and source hash unchanged;
- returns the material to **Ready for Processing**;
- records one bounded public failure code and a separate non-sensitive audit event;
- creates no partial searchable derivative;
- does not retry with relaxed parsing or limits;
- does not trigger OCR, an external service, disclosure, a charge, a scope change, or another workflow.

Authorized personnel retain the alternate ability to review or download the original according to existing access controls.

## Server-controlled worker contract

The client may supply only a legitimate processing purpose. It cannot choose the parser, provide a password, enable repair, raise limits, request OCR, select pages to evade whole-document safety checks, expose attachments, mark output verified, or promote the derivative.

The PDF worker will satisfy the existing pluggable processing contract:

1. receive immutable source bytes and governed source metadata;
2. verify integrity and PDF eligibility;
3. parse within an isolated bounded process;
4. return one bounded derivative payload plus processing facts;
5. perform no database, network, disclosure, billing, authorization, or persistent-storage side effect;
6. let the governed orchestration layer create derivative records and events transactionally.

## Azure and operating-cost posture

The first PDF worker will run locally and only when requested inside the existing production-container allocation. It adds no paid Azure service, standing worker, queue, duplicate permanent file store, OCR service, background compute tier, or external transmission.

Resource limits protect the approved low-cost operating posture and keep graceful degradation explicit. If capacity is unavailable or a PDF exceeds the limits, the source remains available for authorized manual review.

Any future use of Azure AI Document Intelligence, Azure AI Vision, a rendering service, OCR, or another external processor requires a separate cost, privacy, data-location, identity, security, procurement, disclosure, retention, and human-authority review before implementation.

## Required acceptance evidence

The implementation candidate must prove:

- deterministic reconstruction from reviewed source archives;
- successful embedded-text extraction from fictional single-page and multi-page PDFs;
- explicit page boundaries, blank-page preservation, source page labels when present, and bounded page facts;
- original byte and source-hash immutability before and after processing;
- exact source-to-derivative lineage and parser/version recording;
- explicit reading-order, hidden-text, metadata, scanned-page, and semantic-structure uncertainty;
- no OCR, rendering, formula work, attachment access, active-content execution, action activation, external retrieval, shell invocation, or persistent temporary copy;
- encrypted, malformed, repair-dependent, active-feature, embedded-file, excessive-page, oversized-output, timeout, memory-limit, and media-type-mismatch rejection;
- child-process failure isolation and no partial derivative;
- server-controlled limits and rejection of client parser controls;
- tenant, role, sensitivity, and Protected Member access denial;
- independent human review and non-promotion of source truth;
- search exclusion of rejected derivatives;
- portable backup verification and disaster-recovery validation;
- SQLite and PostgreSQL 16 operation;
- production-container execution under the unprivileged identity;
- exact dependency pinning, dependency audit, Bandit, repository hygiene, Azure policy/infrastructure validation, and CodeQL;
- all existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, planning, visual, date/time, and frozen-release regressions.

The test PDFs must be generated as fictional demonstration fixtures during validation. No confidential, personal, Protected Member, investigation, or licensed third-party document may be committed to the repository.

## Deferred sequence

After the PDF embedded-text worker is frozen and tested, Issue #131 should proceed through separate bounded decisions for:

1. image metadata and OCR, including scanned PDF pages;
2. map and geospatial metadata;
3. audio and video transcription;
4. entity, date, and location suggestions;
5. duplicate and relationship analysis;
6. workload routing and broader analyst triage.

Each worker must retain source provenance, uncertainty, access boundaries, human authority, failure isolation, cost controls, and manual operating capability when processing is unavailable.
