# SalCAPA safe image metadata and OCR design

**Status:** Approved engineering design for the next bounded Issue #131 increment  
**Date:** 09 September 2026  
**Applies after:** SalCAPA v3.103  
**Parent requirements:** [Issue #131](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/131) and [Issue #128](https://github.com/Salus-Solutions-LLC/salus-thira-command/issues/128)

## Decision

The next processing increment will add a local, request-driven review worker for single-frame JPEG and PNG source images. It will prepare limited source-stored image metadata and English printed-text optical character recognition (OCR) as a separate derived representation under the v3.103 immutable-source, lineage, access, review, search, audit, backup, and recovery contracts.

The first worker is deliberately narrow. It does not interpret a photograph, identify a person or object, resolve a location, assess a facility, read handwriting, analyze a map, establish evidence, or determine what recognized text means. Scanned-PDF OCR remains deferred because rendering PDF pages introduces a separate parser and rendering boundary that must be designed and validated independently.

The implementation candidate will use exactly pinned and dependency-audited components:

- Pillow for bounded JPEG/PNG identification, validation, decoding, and selected metadata access;
- Tesseract 5 with a fixed English trained-data package for printed-text recognition;
- a fixed SalCAPA orchestration and worker contract that records the exact Pillow, Tesseract, trained-data, and worker versions used.

The dependency versions and container package sources must be rechecked when implementation begins. The design is informed by the following primary documentation:

- [Pillow image-module and decompression-bomb controls](https://pillow.readthedocs.io/en/stable/reference/Image.html)
- [Pillow package record](https://pypi.org/project/pillow/)
- [Tesseract 5 user manual](https://tesseract-ocr.github.io/tessdoc/)
- [Tesseract command-line and TSV output contract](https://tesseract-ocr.github.io/tessdoc/Command-Line-Usage.html)
- [Tesseract release record](https://github.com/tesseract-ocr/tesseract/releases)

## Human and operational purpose

Salus personnel need to find printed words in governed photographs, screenshots, scanned pages, diagrams, and similar records without manually retyping every visible label. The worker prepares a review aid. An authorized person compares that aid with the original image, corrects or rejects it, and decides whether any source information is relevant to later research, assessment, planning, operations, commercial work, or PROVE assurance.

The user-facing lifecycle is:

`Original image → separate image review aid → Awaiting Human Review → Human Reviewed or Rejected`

Human review confirms whether the derived representation is usable for source review. It does not certify the image's authenticity, custody, date, location, authorship, subject identity, completeness, evidentiary value, or current applicability. It also does not establish that OCR text is true merely because characters were recognized.

## Included source material

The first worker will accept only:

- `.jpg` or `.jpeg` with an approved JPEG media type and matching file signature;
- `.png` with an approved PNG media type and matching file signature;
- one non-animated image frame;
- an image whose stored bytes, decoded dimensions, pixel count, metadata sizes, processing time, memory use, and output remain within server-controlled limits;
- material whose stored SHA-256 still matches the governed source record.

The source remains unchanged. The worker may prepare:

- image format and format version when safely available;
- stored width and height;
- decoded color mode and bit-depth facts needed to explain processing;
- frame count and animation-state check;
- EXIF orientation as recorded and whether a deterministic orientation transform was applied to the temporary OCR view;
- presence and bounded size of EXIF, ICC, XMP, comment, and PNG text metadata;
- selected source-stored EXIF values: capture date/time, make, model, software, orientation, and resolution;
- presence of GPS metadata without copying coordinates into the ordinary derivative;
- page-delimited OCR text for the single image;
- bounded line and word-location references derived from Tesseract TSV output;
- recognition-quality indicators that identify text requiring closer comparison with the source.

All selected metadata is labeled **Source-stored image metadata — Unverified**. A capture date is not a verified event date. A device make or model is not proof of who created the image. Orientation and resolution fields do not establish physical scale. GPS presence does not establish where the depicted event occurred.

## OCR boundaries and uncertainty

OCR converts visible pixel patterns into proposed characters. It can omit text, invent characters, merge columns, confuse similar symbols, alter punctuation, misread names and numbers, and produce the wrong order. These errors are especially important in plans, addresses, dates, costs, serial numbers, identifiers, personnel records, facility labels, and investigative material.

The worker must therefore:

- label all recognized text **OCR — Derived and Unverified**;
- preserve a reference to the exact source image and its SHA-256;
- keep line and word regions traceable to source pixel coordinates when emitted;
- describe engine confidence as a recognition-quality indicator, not truth, probability, or evidentiary confidence;
- avoid an unsupported overall accuracy score;
- identify no-text and low-text results as **Text Not Reliably Recognized — Human Review Needed**;
- state the exact selected OCR language and page-segmentation mode;
- state whether EXIF orientation was applied to the temporary OCR view;
- avoid silently deskewing, cropping, sharpening, thresholding, denoising, enhancing, translating, correcting, or completing text;
- avoid inferring tables, form fields, paragraphs, headings, signatures, relationships, identities, prices, hazards, findings, or conclusions.

Search may index OCR text only under the source tenant, role, and sensitivity restrictions. Search matches remain proposed character matches and must take the reviewer back to the original image and its review state.

## Metadata privacy and disclosure controls

Image metadata can disclose personal, operational, facility, device, time, and location information that is not visually obvious. The first derivative will minimize metadata rather than copy every tag.

- Exact GPS coordinates, camera-owner strings, maker notes, embedded thumbnails, arbitrary comments, and unknown private tags are not copied into ordinary searchable text.
- GPS presence is recorded as a restricted processing fact. Coordinate parsing and map use remain deferred to the separately governed geospatial increment.
- Metadata never lowers the source sensitivity or expands its authorized audience.
- Protected Member views cannot reveal Salus-internal information, another member's material, hidden metadata, device details, or location data outside the approved disclosure scope.
- A human-authorized disclosure must use a governed approved record, not the unreviewed OCR or metadata derivative by itself.
- Removing metadata from a future export does not alter the immutable original. Export sanitization remains a separate governed action with its own evidence.

## Explicit exclusions

The first image/OCR worker will reject or defer:

- GIF, WebP, HEIC/HEIF, AVIF, BMP, TIFF, camera RAW, SVG, EPS, PostScript, DICOM, Photoshop, layered, vector, or other image formats;
- animated, multi-frame, tiled, pyramidal, unusually deep, palette-ambiguous, truncated, malformed, repair-dependent, or decompression-bomb images;
- PDFs and PDF-page rendering, including image-only or scanned PDF pages;
- password-protected or encrypted containers;
- embedded thumbnails, attachments, profiles, scripts, URLs, linked resources, or remote content retrieval;
- XMP or EXIF packet preservation beyond approved bounded fields;
- handwriting recognition, signature recognition or validation, translation, language detection, or non-English recognition;
- facial detection or recognition, biometric processing, person identification, emotion inference, demographic inference, vehicle or license-plate identification;
- object, weapon, damage, hazard, vulnerability, threat, behavior, scene, or activity classification;
- map interpretation, coordinate extraction, geocoding, routing, or geospatial conclusions;
- image enhancement intended to reveal obscured or hidden content;
- generative completion, captioning, visual question answering, or unsupported description;
- evidentiary authentication, manipulation detection, provenance certification, or chain-of-custody conclusions;
- entity, date, location, allegation, relationship, duplicate, price, cost, or investigative conclusions.

Unsupported material remains immutable and available to authorized personnel for manual review or a later approved worker.

## Decode and resource controls

Image decoding and OCR will not run inside the web process. The governed orchestration layer starts a fixed child-process entry point without a shell and with a minimal environment. Before OCR, the child process must:

1. verify the approved extension, media type, file signature, and source hash;
2. restrict Pillow to the expected JPEG or PNG decoder rather than format auto-discovery;
3. convert Pillow decompression-bomb warnings into processing failures;
4. verify the image structure, reopen it, and fully decode it within the child limits;
5. reject an unexpected format, additional frame, animation, truncated source, or unsafe metadata size;
6. create a clean temporary OCR view containing decoded pixels only, with no copied EXIF, XMP, ICC, comment, text-chunk, thumbnail, or linked metadata;
7. invoke a fixed Tesseract binary directly without a shell, plugin, wrapper-selected executable, or client-selected argument;
8. remove the temporary directory after success or failure.

The only permitted pixel changes in the initial worker are a recorded EXIF-orientation transform and deterministic conversion to an OCR-compatible color mode. The worker will not resize an oversized image to evade limits; it fails closed.

Initial implementation limits will be conservative and server controlled:

- maximum stored source size: 16 MiB;
- maximum width or height: 8,000 pixels;
- maximum decoded pixels: 16,000,000;
- maximum frames: 1;
- maximum accepted source metadata considered: 1 MiB aggregate;
- maximum copied value for any approved metadata field: 1,024 characters;
- maximum OCR characters: 500,000;
- maximum TSV/output bytes: 8 MiB;
- maximum wall time: 45 seconds;
- maximum CPU time: 30 seconds;
- maximum child-process address space: 512 MiB;
- maximum open files: 64;
- OCR language: English only;
- OCR engine mode, page segmentation mode, decoder allowlist, and all resource limits selected by the server.

The implementation may lower these limits to remain safe within the approved low-cost container. Raising a limit, adding a format or language, or enabling preprocessing requires a reviewed change and fresh gates. A resource-limit failure is not retried with weaker controls.

## Tesseract execution boundary

The worker will execute an exact Tesseract binary installed from the reviewed production-container source. It must verify and record the binary version and approved English trained-data identity at startup or processing time. The invocation uses a fixed argument list, no shell, a new empty working directory, a minimal environment, no user configuration files, and no client-provided OCR options.

Tesseract will receive only the clean temporary pixel-only image, not the original source file. It may return bounded TSV data through an approved temporary output or pipe. SalCAPA will validate TSV columns, numeric bounds, pixel regions, text encoding, record count, and total size before producing the derivative.

The worker must not:

- permit configuration files, word lists, patterns, language packs, page-segmentation choices, output renderers, debug paths, or executable paths supplied by a client;
- produce a searchable PDF, hOCR, ALTO, PAGE XML, rendered image, or modified source in the first increment;
- load user home-directory state or system-wide writable configuration;
- make a network request or invoke another executable;
- write outside the worker's temporary directory;
- treat an OCR confidence value as certainty about content or meaning.

## Derived records and provenance

One successful job creates an **Image Metadata and OCR Review Aid** derivative using the existing transactional processing contract. It records:

- tenant and source material;
- exact source and derivative SHA-256 values;
- source extension, media type, and detected format;
- exact worker, Pillow, Tesseract, and trained-data versions or hashes;
- stored and OCR-view dimensions;
- applied orientation and color-mode conversion facts;
- selected metadata fields and restricted-metadata presence facts;
- OCR language, segmentation mode, line/word counts, truncation state, and recognition-quality facts;
- creation date and time;
- uncertainty and limitation notes;
- review status and reviewer lineage.

The derived record remains **Derived — Unverified** and **Awaiting Human Review**. An independent reviewer may mark the representation **Human Reviewed** or **Rejected**. Review changes only the representation-review state; it cannot silently promote source authenticity, intelligence qualification, a finding, threat judgment, plan approval, cost validation, price approval, disclosure authority, or operational authority.

A corrected transcription is a new governed derivative linked to both the original image and the OCR derivative. Corrections do not overwrite the OCR output or the original. A later source version creates new processing lineage and cannot rewrite a historical derivative or the source basis of an approved record.

## Failure behavior

No derivative is created unless the child completes and the orchestration layer validates source integrity, approved type, worker identity, version facts, decoded dimensions, frame count, metadata bounds, OCR output structure, pixel-coordinate bounds, output limits, and derivative hash.

A format, decode, metadata, OCR, resource, malformed-output, version, or integrity failure:

- leaves the original bytes and source hash unchanged;
- returns the source to **Ready for Processing**;
- creates no partial searchable derivative;
- records one bounded public failure code and a separate non-sensitive audit event;
- does not retry with another decoder, higher limit, different OCR mode, external service, or relaxed validation;
- does not start PDF rendering, language detection, image interpretation, disclosure, billing, scope change, or another workflow.

Authorized personnel retain manual access to the original according to existing tenant, role, sensitivity, and disclosure controls.

## Server-controlled and human-authority contract

The client may provide only a legitimate processing purpose. It cannot select the decoder, OCR engine, language, model, trained data, confidence threshold, preprocessing, executable, output format, limits, metadata fields, disclosure scope, or review state.

The worker performs no database, network, authorization, billing, disclosure, notification, workflow, finding, assessment, planning, or operational side effect. The governed orchestration layer creates the source-linked derivative and audit events transactionally.

Salus personnel retain professional judgment and all qualification, correction, approval, release, disclosure, legal, policy, commercial, investigative, and operational authority.

## Azure and operating-cost posture

The first worker runs locally and only when requested within the existing production-container allocation. It adds no paid Azure AI service, standing worker, queue, background-compute tier, duplicate permanent source store, or external transmission.

Pillow, Tesseract, and the English trained-data package will increase the production image size and may increase cold-start and request CPU use. The implementation candidate must measure image-size growth, bounded OCR runtime, memory use, and container behavior before release. If those measurements cannot fit the existing low-cost posture, OCR remains unavailable while original-image review continues; the implementation must not silently provision a paid service.

Any future Azure AI Vision, Azure AI Document Intelligence, external OCR, broader language, GPU, queue, persistent worker, or third-party model requires a separate cost, identity, privacy, data-location, retention, procurement, security, disclosure, and human-authority review.

## Required acceptance evidence

The implementation candidate must prove:

- deterministic reconstruction from reviewed source archives;
- successful bounded metadata and English printed-text OCR from fictional demonstration JPEG and PNG records;
- exact original-byte and source-hash immutability before and after processing;
- exact source-to-derivative lineage and complete worker, decoder, OCR-engine, and trained-data version evidence;
- explicit OCR, metadata, orientation, character-order, number/name, and recognition-quality uncertainty;
- safe handling of no-text and low-text images;
- correct source-pixel traceability for any emitted OCR region;
- no client-selected executable, language, model, trained data, configuration, preprocessing, output renderer, metadata scope, or limit;
- no copied hidden GPS coordinates, maker notes, thumbnails, arbitrary private tags, or oversized metadata;
- no network access, external retrieval, script execution, image interpretation, facial/biometric work, object classification, map interpretation, PDF rendering, or persistent temporary file;
- mismatch, malformed, truncated, animated, multi-frame, unsupported-format, decompression-bomb, excessive-dimension, excessive-pixel, metadata-limit, timeout, memory-limit, invalid-TSV, version-mismatch, and OCR-failure rejection;
- child-process failure isolation and no partial derivative;
- tenant, role, sensitivity, disclosure, and Protected Member access denial;
- independent representation review without promotion of source truth or authority;
- correction/supersession lineage without overwriting the original or OCR result;
- search exclusion of rejected derivatives and source-linked return from accepted matches;
- portable backup verification and disaster-recovery validation;
- SQLite and PostgreSQL 16 operation;
- production-container execution under the unprivileged identity;
- measured production-image size and bounded CPU/memory behavior;
- exact dependency and container-source pinning, dependency audit, Bandit, repository hygiene, Azure policy/infrastructure validation, and CodeQL;
- all existing SalINTEL, SalTHIRA, SalCAPA, SalOPS, PROVE, commercial, investigation, emergency-planning, visual, date/time, and frozen-release regressions.

Test images must be created as fictional demonstration fixtures during validation. No confidential, personal, Protected Member, investigation, or licensed third-party image may be committed to the repository.

## Deferred sequence

After the standalone JPEG/PNG worker is frozen and tested, Issue #131 should proceed through separate bounded decisions for:

1. scanned-PDF page rendering and OCR;
2. broader image formats and languages;
3. map and geospatial metadata;
4. audio and video transcription;
5. entity, date, and location suggestions;
6. duplicate and relationship analysis;
7. workload routing and broader analyst triage.

Each worker must preserve immutable sources, exact lineage, uncertainty, tenant and sensitivity boundaries, human authority, failure isolation, cost controls, and manual operating capability when processing is unavailable.
