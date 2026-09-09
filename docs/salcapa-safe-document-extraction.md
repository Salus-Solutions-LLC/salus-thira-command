# SalCAPA safe document extraction design

**Status:** Approved engineering design for the next bounded Issue #131 increment  
**Date:** 09 September 2026  
**Applies after:** SalCAPA v3.101  
**Parent requirements:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128)

## Decision

The next processing increment will add a local, non-executing Office Open XML worker for governed `.docx`, `.xlsx`, and `.pptx` source material. It will reuse the v3.101 source, derivative, lineage, review, search, access-control, audit, backup, and recovery contracts.

This is deliberately not a general document-conversion service. It extracts readable text and limited document metadata from approved package parts without opening the document in Microsoft Office, evaluating formulas, following relationships, retrieving external content, or running active content.

## Human and operational purpose

Salus personnel need to locate and review information already held in governed Word, Excel, and PowerPoint records without uploading a second converted copy. The worker prepares a source aid for authorized review. It does not decide what the information means, qualify intelligence, establish a finding, approve a plan, set a price, or authorize disclosure.

The user-facing state remains:

`Original source → separate derived representation → Awaiting Human Review → Human Reviewed or Rejected`

Human review confirms whether the representation is usable for source review. It does not certify that the source is true or current.

## Included formats and content

### Word documents

For `.docx`, extract text from approved document parts only:

- main document;
- headers and footers;
- footnotes and endnotes;
- comments when present.

Paragraph, table-cell, tab, and line-break boundaries must remain understandable. Tracked insertions and deletions may be represented, but the derivative must identify that revision markup was present and must not silently resolve competing revisions.

### Excel workbooks

For `.xlsx`, extract:

- workbook and worksheet names;
- shared strings and inline strings;
- displayed cell values and cached formula results when present;
- limited core document properties.

The worker must never calculate or recalculate a formula, invoke a data connection, refresh a query, run a macro, resolve an external workbook link, or infer that a cached result remains correct. Formula cells must be labeled as formulas, and cached values must be identified as source-stored values.

### PowerPoint presentations

For `.pptx`, extract text from:

- slides in governed presentation order;
- speaker notes when present;
- limited core document properties.

The worker must not play media, activate actions, follow hyperlinks, run embedded content, or infer meaning from visual layout. Text order is a processing approximation and remains subject to human review.

## Explicit exclusions

The first document worker will reject or defer:

- macro-enabled `.docm`, `.xlsm`, and `.pptm` packages;
- legacy binary `.doc`, `.xls`, and `.ppt` files;
- password-protected or encrypted packages;
- malformed or ambiguous ZIP packages;
- embedded OLE objects, executables, scripts, add-ins, and ActiveX content;
- external links, remote images, linked templates, data connections, and refresh operations;
- formula evaluation;
- PDF text extraction;
- OCR, image interpretation, map/geospatial interpretation, audio, and video;
- entity, person, threat, relationship, or duplicate conclusions.

Unsupported material remains unchanged and available for human review or a later compatible worker.

## Package safety controls

Before any XML is parsed, the worker must apply fail-closed controls:

- verify the stored source SHA-256 against the governed source record;
- require an approved extension and matching package content type;
- reject encrypted entries and unsafe path names;
- reject absolute paths, parent traversal, duplicate normalized paths, and ambiguous package members;
- enforce limits on source size, entry count, individual entry size, total expanded size, and compression ratio;
- read only an allowlist of package parts;
- ignore relationships for retrieval purposes and never make a network request;
- parse XML with hardened non-resolving behavior;
- impose limits on extracted characters and XML complexity;
- create no derivative if any integrity or safety check fails.

A processing failure returns the source to **Ready for Processing**, records a bounded public failure code, creates an audit event, and never alters or erases the original.

## Derived records and provenance

One processing job may create an **Extracted Document Text** derivative and a separate **Document Metadata** derivative. Each derivative must record:

- tenant and source material;
- exact source SHA-256;
- exact derivative SHA-256;
- processor name and version;
- extraction method and format;
- package parts used;
- creation date and time;
- truncation state;
- uncertainty and limitation notes;
- review state and reviewer lineage.

Search results must continue to inherit tenant, role, and sensitivity restrictions from the source. Rejected derivatives are excluded from ordinary search. A later source version creates a new source record or governed version reference and new derivatives; it must not rewrite the historical basis of an approved record.

## Metadata boundaries

Limited package metadata may include title, subject, author-as-recorded, keywords, description, category, creation time, and modified time. It is reported as source-stored metadata, not independently verified identity or chronology.

Metadata must not be treated as proof of authorship, custody, ownership, authenticity, approval, or recency. Personal information and investigation content remain subject to the source sensitivity and disclosure controls.

## Worker contract

The processor-selection decision remains server controlled. Client requests may provide only a legitimate purpose; they cannot select a processor, bypass limits, mark output verified, or promote the result.

The worker must satisfy the existing pluggable processing contract:

1. receive immutable source bytes and governed source metadata;
2. verify integrity and format eligibility;
3. return bounded derivative payloads plus processing facts;
4. perform no database, network, disclosure, billing, or authorization side effects;
5. let the governed orchestration layer create derivative records and events transactionally.

This separation allows future PDF, OCR, photo/map, transcription, and specialist workers without weakening the source-record contract.

## Azure and operating-cost posture

The first Office Open XML worker will use local package/XML processing within the existing production container. It adds no Azure paid service, background compute tier, persistent duplicate-file store, or standing processing resource.

Processing remains request-driven and bounded. A future decision to use Azure AI Document Intelligence, Azure AI Vision, speech services, or another external processor requires separate cost, privacy, data-location, identity, disclosure, and approval review before implementation.

## Required acceptance evidence

The implementation candidate must prove:

- deterministic reconstruction from reviewed source archives;
- successful `.docx`, `.xlsx`, and `.pptx` extraction using fictional demonstration records;
- original byte and source-hash immutability before and after processing;
- macro-enabled, encrypted, malformed, traversal, oversized, excessive-entry, and expansion-ratio rejection;
- no relationship retrieval, network access, formula calculation, script execution, or embedded-object execution;
- exact source-to-derivative lineage and processor/version recording;
- explicit formula-cache and revision-markup uncertainty;
- tenant, role, sensitivity, and Protected Member access denial;
- independent human review and non-promotion of source truth;
- search exclusion of rejected derivatives;
- portable backup verification and disaster-recovery validation;
- SQLite and PostgreSQL 16 operation;
- production-container execution;
- dependency audit, Bandit, repository hygiene, Azure policy/infrastructure validation, and CodeQL;
- all existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, planning, visual, date/time, and frozen-release regressions.

## Deferred sequence

After the Office Open XML slice is frozen and tested, Issue #131 should proceed through separate bounded decisions for:

1. PDF text and structural extraction;
2. image metadata and OCR;
3. map and geospatial metadata;
4. audio and video transcription;
5. entity/date/location suggestions;
6. duplicate and relationship analysis;
7. workload routing and broader analyst triage.

Each worker must retain source provenance, uncertainty, access boundaries, human authority, failure isolation, cost controls, and the ability to operate manually when processing is unavailable.
