# Salus Solutions — Current Handoff

**Updated:** 23 September 2026
**Active Azure development demonstration release:** SalCAPA 3.175
**Frozen source:** `release/v3.175` at `62b3fbc5089b237ee6aee044de84ace699b08d66`
**Immutable running image:** `salcapadevb48224acr.azurecr.io/salcapa@sha256:3c51917d148a231f91a0722b5704fd10b038925da66c32ccce051988c9553a50`
**Rollback:** SalCAPA 3.174, source `a3b9abece87d328ebb272e8c15065c25f41a57ba`, image `sha256:d9067d74d7a4f7a1bd62138329362e1cde9928c95b14ff54ae7ef08197628291`
**Authoritative repository:** `Salus-Solutions-LLC/salus-thira-command`
**Working branch:** `development/salcapa-platform`

## Objective and accepted work

Finish automatic processing, hash-verified promotion to SharePoint `Salus Knowledge Sources`, and movement into OneDrive `SalCAPA Intake / 90 Processed Intake` for the two real files still under `10 Pending Classification`. SAL-D022 governs no-exception intake, retention of originals and citation metadata, automatic retries, and human authority for consequential use.

The 3.174 build reconstruction silently overwrote the reviewed PDF worker and its regression test with older archived source. The 3.175 build verifies the reviewed worker and test bytes and runs the PDF active-feature regression inside the production image. CI run `35820421893` passed general validation, PostgreSQL, and container runtime on the exact frozen commit. Image publication run `35820754625` succeeded. Governed application deployment run `35821037619` passed the exact digest, live readiness, identity/sign-in, isolated Microsoft 365 intake acceptance, and cleanup. Activation commit `433e177595587f60315bc5e220f6da5bdc3dbfb6` was followed by workflow pin correction `c468081f45f63f5a154c93f88962f510ed0905df`; only the latter deployment run succeeded. The first deployment attempt failed its pre-Azure activation check and did not change the running app.

Live scoped diagnostic run `35821550222` used the running 3.175 image. It found both pending files; DOCX and PDF each reported `Complete` extraction. The PDF worker reported no active-feature rejection. The destination read returned HTTP 200, while a harmless write to `05 Research and Reference` returned Graph HTTP 403 `accessDenied`. The processor readiness state reported two discovered, zero promoted, and only `destination_write_denied` retries. The temporary diagnostic job was removed. Neither real file has been verified in the knowledge destination or processed archive.

## Remaining access action

The target site is `salussolutions.sharepoint.com,69947f9a-c94c-43e9-8604-b73dc5c4360d,85462e8c-ac01-4a1f-b5a9-31608606e68d` (`https://salussolutions.sharepoint.com/sites/SalusKnowledgeSources`). SalCAPA's Graph application client ID is `c2fc227a-7ba4-467d-a6c6-8a0f9b813aee`. A protected read-only inspection by the Azure deployment identity returned HTTP 401 from Graph on `/sites/{site-id}/permissions`, so that identity cannot inspect or grant this permission. No site grant was changed. Use an authorized Microsoft 365/SharePoint administrator to inspect existing application grants and, if `write` is absent, grant `write` to this exact application on this exact site under the existing Sites.Selected model. Do not grant tenant-wide write or duplicate an existing site grant.

The user explicitly authorized Graph Explorer sign-in as `MDuncan@salus.solutions` and later authorized presenting both saved accounts in the secure chooser. The secure chooser selected only `MDuncan@salus.solutions`; the password step returned submitted, then the Microsoft popup closed. Graph Explorer and a fresh verification tab stopped responding, so sign-in success is unknown. No site grant was inspected or changed. Browser recovery also stalled. The separate Global Admin saved identity is `MDuncan@SALUSSolutions.onmicrosoft.com`; it was not selected or used. The SharePoint connector does not expose application site-grant operations. The browser's confirmation policy requires confirmation at action time before materially expanding app access. Resume only when a working authenticated administrator path is available; inspect the existing site grants first.

## Single best next action

After the narrow site grant is made, verify a harmless application-identity write and cleanup, then let SalCAPA retry both real files. Confirm each exact original and citation record, destination SHA-256 verification, no duplicate destination, and movement to `90 Processed Intake`; confirm the pending queue is clear and retain the 3.174 rollback.

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
