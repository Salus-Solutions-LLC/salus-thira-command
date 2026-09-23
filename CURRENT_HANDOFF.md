# Salus Solutions — Current Handoff

**Updated:** 23 September 2026
**Active Azure development demonstration release:** SalCAPA 3.174
**Frozen source:** `release/v3.174` at `a3b9abece87d328ebb272e8c15065c25f41a57ba`
**Activation:** `568acd07dae508c0df0e7c82977bee25adc14706`
**Immutable running image:** `salcapadevb48224acr.azurecr.io/salcapa@sha256:d9067d74d7a4f7a1bd62138329362e1cde9928c95b14ff54ae7ef08197628291`
**Rollback:** SalCAPA 3.173
**Authoritative repository:** `Salus-Solutions-LLC/salus-thira-command`
**Development branch after diagnostic source edit:** `7b247d5072d3fae0f09b71e39f576789c38c5e34`

## Current objective and evidence

Complete automatic processing, destination verification, and archival of both real files under OneDrive `SalCAPA Intake / 10 Pending Classification`. The governed 3.174 deployment run `35815980228` succeeded, including readiness, sign-in, isolated Microsoft 365 acceptance, and temporary job cleanup. The 3.174 code preserves originals and retry obligations when extraction cannot finish; its PDF worker accepts empty annotation arrays and still blocks actual active features. No new application image has been deployed since 3.174.

The scoped live diagnostic run `35817510244` found two pending files and zero promotions. DOCX extraction completed. PDF extraction still reports `PDF_ACTIVE_CONTENT`; direct worker diagnostic classified its reason as `other`, so the precise live PDF feature is unresolved. The application identity read the knowledge destination successfully but a harmless write to `Salus Knowledge Sources / 05 Research and Reference` returned Graph HTTP 403 `accessDenied`. The diagnostic job was removed.

A source-only diagnostic commit `7b247d5` added bounded structural flags for the PDF; it did not change the running 3.174 image. Its triggered run `35819127268` completed and removed the temporary diagnostic job. The workflow's existing log filter did not include the new flags, so this run cannot establish their values. Automatic approval review rejected the proposed workflow edit to print those flags because the workflow would launch a managed-identity job that reads internal documents and attempts a Graph write/delete. Do not bypass that rejection. No SharePoint site permission has been changed, and no real file has been verified in the knowledge destination or processed archive.

## Single best next action

Obtain explicit approval for the bounded live workflow change after reviewing its cloud-side effects, then identify the PDF structure from allowlisted diagnostic output. Separately, use an authorized Microsoft 365 administrator to verify the SalCAPA application's site-scoped role on the exact `Salus Knowledge Sources` site and apply the narrow write grant only if missing; verify a harmless write and cleanup before retrying the two real files. Do not infer the exact permission fault solely from HTTP 403.

---

## Earlier handoff (historical; superseded by the update above)

# Salus Solutions — Current Handoff

**Handoff date:** 23 September 2026  
**Current production release:** SalCAPA 3.171  
**Accepted source commit:** `66b500dbfb8901b8c910a3667605750102e140dd`  
**Activation commit:** `9d3ac13bf3037f26d67ea5959d460d5e603a97b6`  
**Immutable image:** `salcapadevb48224acr.azurecr.io/salcapa@sha256:55998773f4f3f7d55daed251a044432e5932f6a3815d13648c88d3363d0c7d24`  
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

The live check after v3.170 found `Executive Protection.docx` still in `10 Pending Classification`. v3.170 corrected the PostgreSQL identity-return defect, but the second live check established that `register_knowledge_promotion` was not imported or invoked by `salcapa_runtime.py`; therefore the routes and scheduled startup processor were absent. SalCAPA 3.171 registers the processor with the live FastAPI application and adds runtime-composition regression assertions. v3.171 passed governed deployment run `35809337948`. After its first scheduled cycle, both pending files remained in `10 Pending Classification`, `90 Processed Intake` remained empty, and no destination copy of `Executive Protection.docx` was discoverable. The remaining fault is therefore inside the live processing/promotion transaction and requires production-state diagnostics, including destination-library read/write authority. Confirm the candidate reaches `Ingested and Verified`, appears in `05 Research and Reference`, and is moved to `90 Processed Intake` only after destination hash verification.

## Known constraints

- Active content is never executed.
- Encrypted, corrupt, resource-limited, or not-yet-decodable components remain preserved and automatically retried; they do not enter a human exception queue.
- Automatic ingestion does not authorize external publication, Protected Member disclosure, final findings, formal recommendations, risk acceptance, or methodology changes.

## Single best next action

Add a governed live diagnostic/acceptance step for the knowledge destination and inspect the candidate retry reason before changing permissions or promotion behavior.
