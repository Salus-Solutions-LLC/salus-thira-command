# Salus Solutions — Current Handoff

**Handoff date:** 23 September 2026  
**Current production release:** SalCAPA 3.169  
**Release in preparation:** SalCAPA 3.170 PostgreSQL ingestion hotfix  
**Accepted source commit:** `729a48c3ec45a6ae98a57f9de8bc18d2d8a68b40`  
**Activation commit:** `0932fff09f0606576ee728dae5191339ee2e1e77`  
**Immutable image:** `salcapadevb48224acr.azurecr.io/salcapa@sha256:6b1693aa6321b9abcc8983d79b3e701ee112e29432c600357978c33f62de708f`  
**Rollback release:** SalCAPA 3.168  
**Authoritative repository:** `Salus-Solutions-LLC/salus-thira-command`  
**Working branch:** `development/salcapa-platform`

## Current objective

Release SalCAPA 3.169 with automatic, complete, no-exception knowledge processing for every file beneath **OneDrive → SalCAPA Intake → 10 Pending Classification**.

## Approved governing decision

SAL-D022 supersedes SAL-D021. Every file is automatically captured, hash-bound, extracted through the safe multiformat processing chain, classified, promoted, destination-hash verified, and moved to `90 Processed Intake`. Conditions that previously caused exception review are metadata flags. Processing limitations create automatic retry obligations. Originals and citation metadata are retained and files are never automatically deleted. Human authority remains required for consequential use and disclosure, not ingestion.

## Implemented for v3.169

- Removed format, duplicate, sensitivity, and classification-confidence ingestion gates.
- Added automatic bounded classification with a `05 Research and Reference` fallback.
- Connected intake classification to the existing TXT/CSV/JSON/XML/EML, Office Open XML, PDF, image OCR, and audio/video processing chain.
- Preserved extracted text, extraction lineage, processor identity, hashes, truncation status, and processing flags in the candidate classification record.
- Added structured citation metadata: document title, authors, source-created and modified dates, last modifier, OneDrive owner, item ID, relative path, trusted URL, eTag/cTag, MIME type, SHA-256 citation key, and format-appropriate locator scheme.
- Added automatic retry status and events instead of exception review.
- Added a 60-second scheduled processor when all governed Microsoft 365 identifiers are configured.
- Preserved destination SHA-256 verification, source eTag protection, immutable audit events, movement to `90 Processed Intake`, and the prohibition on automatic deletion.
- Verified `Executive Protection.docx` extracts completely, retains `Nikey Prijono` as source-stored creator and last modifier, retains its created/modified dates, and classifies to `05 Research and Reference` without an ingestion exception.

## Validation completed before commit

- Python static compilation passed for the modified knowledge processor and smoke test.
- `tools/ci_m365_knowledge_promotion_smoke.py` passed in an isolated environment using pinned application dependencies.
- The attached `Executive Protection.docx` produced complete derived text and structured citation metadata through `SalCAPA Safe Office Document Extractor`.

## Release evidence

- CI run `35803637173` completed successfully for the exact frozen source.
- `release/v3.169` was frozen at `729a48c3ec45a6ae98a57f9de8bc18d2d8a68b40`.
- Immutable image publication run `35804087198` completed successfully.
- Governed Azure application deployment run `35804334144` completed successfully, including readiness, identity/configuration checks, isolated Microsoft 365 intake acceptance, and cleanup.
- v3.168 remains the accepted rollback release and immutable rollback image.

## Remaining operational confirmation

The live check found `Executive Protection.docx` still in `10 Pending Classification`. Diagnosis identified that the PostgreSQL insert path did not return the new knowledge-candidate ID, so the first audit-event insert failed. SalCAPA 3.170 uses an explicit cross-database `RETURNING id` clause, fails closed if no identity is returned, and adds regression assertions. After deployment, confirm the candidate reaches `Ingested and Verified`, appears in `05 Research and Reference`, and is moved to `90 Processed Intake` only after destination hash verification.

## Known constraints

- Active content is never executed.
- Encrypted, corrupt, resource-limited, or not-yet-decodable components remain preserved and automatically retried; they do not enter a human exception queue.
- Automatic ingestion does not authorize external publication, Protected Member disclosure, final findings, formal recommendations, risk acceptance, or methodology changes.

## Single best next action

Validate and deploy the v3.170 PostgreSQL ingestion hotfix, then confirm the live candidate record and destination/archive locations for `Executive Protection.docx`.
