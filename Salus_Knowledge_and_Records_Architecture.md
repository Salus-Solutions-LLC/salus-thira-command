# Salus Knowledge and Protected Member Records Architecture

**Decision status:** Approved target design, based on the live Microsoft 365 inventory and the deployed SalCAPA intake, processing, review, and indexing controls reviewed on 22 September 2026.

**Implementation status — 22 September 2026:** The eleven approved enterprise-knowledge folders were created and verified in **SharePoint → Salus Knowledge Sources → Documents**. The four approved workflow folders were created and verified in **OneDrive → SalCAPA Intake**. Separate SharePoint document libraries named **Protected Member Records** and **System Governance** were created and verified in the private SalCAPA site. The site displays one member, Marc Duncan, so the initial effective access boundary is Marc only. No existing business content was moved or deleted. The existing empty `Protected Member Records` folder in the general SalCAPA Documents library remains distinct from the new library and is not an approved records destination.

## Executive decision

Salus should use three deliberately separate content zones:

1. **Enterprise knowledge:** SharePoint site **Salus Knowledge Sources** is the authoritative long-term home for approved Salus doctrine, methodologies, capabilities, templates, research, policies, training, and reusable examples.
2. **Governed intake:** OneDrive folder **SalCAPA Intake** is a temporary, controlled drop zone for files awaiting capture, classification, processing, and human review. It is not the permanent knowledge library.
3. **Protected Member records and outputs:** Protected Member source records must be segregated by member and engagement. Issued reports remain in **SalCAPA → Protected Member Reports**. Member-specific source material must not be mixed into the enterprise knowledge library.

ChatGPT and SalCAPA may use the same approved enterprise knowledge corpus, but they reach it through different governed access paths. A file being stored does not automatically make it approved, searchable, indexed, or authoritative.

## Where to upload now

Until automated promotion and the final SharePoint permissions are implemented and validated, upload new candidate knowledge files to:

**OneDrive → SalCAPA Intake → 10 Pending Classification**

This subfolder is now created and verified. New candidate knowledge uploads should no longer be placed at the root of **SalCAPA Intake**.

Do not upload enterprise knowledge to **SalCAPA Intake - Governed- DO NOT USE**, **Protected Member Reports**, or the general **SalCAPA** Documents library.

## Target Microsoft 365 structure

### A. SharePoint: Salus Knowledge Sources

Use this site only for reusable, enterprise-wide knowledge. Its Documents library should contain:

- `01 Salus Doctrine and Methodologies`
- `02 Service Capabilities`
- `03 Assessment Standards and Templates`
- `04 Approved Examples`
- `05 Research and Reference`
- `06 Policies and SOPs`
- `07 Training and Exercises`
- `08 Visual Media`
- `09 Historical Material`
- `10 Pending Classification`
- `99 Superseded and Retained`

Recommended metadata:

- Knowledge domain
- Document type
- Status: Pending Review / Approved / Superseded / Rejected
- Owner
- Effective date and review date
- Sensitivity/classification
- Source/provenance
- SalCAPA processing status
- Human-review status
- SalINTEL indexing status
- Supersedes / superseded by
- Permitted products: ChatGPT, SalCAPA, SalINTEL, SalTHIRA, SalOPS

Only approved, human-reviewed content should become part of the active enterprise knowledge corpus. Historical material should remain discoverable but should not silently outrank current doctrine.

### B. OneDrive: SalCAPA Intake

This is a short-lived staging queue, not a records repository. Use these folders:

- `10 Pending Classification`
- `20 Ready for Intake Review`
- `30 Exceptions and Manual Review`
- `90 Migration Hold`

SalCAPA should continue to capture exact source bytes and provenance from its configured intake root. Movement out of intake must occur only after successful capture, reconciliation, and retention verification.

### C. SharePoint: SalCAPA

Use separate libraries with separate purposes:

- **Protected Member Reports** — issued/generated reports and delivery artifacts; retain.
- **Protected Member Records** — recommended new restricted library for engagement source records, evidence, correspondence, and working records. Organize by immutable member ID and engagement ID, not only by display name.
- **System Governance** — recommended restricted library for approved templates, release evidence, acceptance records, configuration records, and operational governance artifacts that are not general enterprise knowledge.

Recommended Protected Member record path:

`Protected Member Records / PM-{member-id} / ENG-{engagement-id} / 01 Source / 02 Submitted / 03 Reviewed / 04 Deliverables / 05 Correspondence`

Permissions must be enforced at the library or approved security-boundary level. Avoid ad hoc item-level sharing as the primary design.

## SalCAPA and ChatGPT use model

### SalCAPA

SalCAPA should:

- read only from the configured intake boundary;
- preserve the original, SHA-256 hash, Microsoft item identity, version/eTag, path, timestamps, owner, and classification;
- require human approval before processing or indexing;
- bind every derivative to the exact source hash;
- require a different authorized reviewer before a derivative becomes human reviewed;
- require separate authority before SalINTEL indexing or routing to another Salus product;
- maintain tenant and clearance boundaries;
- never treat extraction, OCR, transcription, or indexing as a finding, decision, disclosure approval, or operational authority.

### ChatGPT

ChatGPT should be connected only to the approved **Salus Knowledge Sources** corpus and, where explicitly authorized, narrowly scoped Protected Member engagement content. Enterprise knowledge and member records should not be exposed through one broad connector scope. SharePoint remains the authoritative source; ChatGPT is a governed consumer, not the system of record.

## Supported-content matrix

| Content | Governed processing posture | Important limits |
|---|---|---|
| TXT, MD, CSV, TSV, JSON, XML, LOG, EML | Native strict text extraction | Derived text capped at 2,000,000 characters |
| DOCX, XLSX, PPTX | Non-executing Open XML extraction | Embedded/active content rejected; formulas are not recalculated; human review required |
| DOC, XLS, PPT, DOCM, XLSM, PPTM | Stored original may be retained, but automated processing is blocked | Convert an approved copy to modern non-macro format; retain original for provenance |
| PDF | Isolated embedded-text extraction | 64 MB processor limit; encrypted or active-content PDFs rejected; selected-page rendering is separately governed |
| JPG, JPEG, PNG | Metadata and printed-text OCR | 16 MB processor limit; one frame; OCR does not perform interpretation, identity, biometrics, or handwriting recognition |
| Handwriting/difficult text | Separate request-driven local review | Requires an installed approved profile and independent human review |
| WAV, MP3, MP4 | Isolated English spoken-word transcription | 128 MB processor limit, up to 3,600 seconds; no speaker identity, biometrics, emotion, translation, or video-frame analysis |
| Other formats | May be preserved by intake if within intake controls, but are not automatically searchable | Manual review or a separately approved processor is required |

The Microsoft intake hard cap is 100 MB per file and the currently documented deployment default is 25 MB. Processor-specific limits may be lower. A folder traversal is bounded to 20 levels and 2,000 discovered items; large migrations must therefore be staged in controlled batches.

## Existing-content disposition

| Existing location | Decision now | Final action after validation |
|---|---|---|
| SharePoint **Salus Knowledge Sources** | Retain | Make authoritative enterprise knowledge site and implement target taxonomy/metadata |
| SharePoint **SalCAPA → Protected Member Reports** | Retain | Continue as issued report destination |
| SharePoint **SalCAPA → Documents** | Retain during migration | Classify and migrate reusable knowledge, member records, and governance material into their correct destinations |
| `SALUS/SalCAPA Library - Upload Staging` | Retain during migration | Inventory, de-duplicate by hash, migrate approved material, then archive or delete only after reconciliation |
| OneDrive **SalCAPA Intake** | Retain | Continue as the only governed temporary intake root until a deliberate rebind is deployed and accepted |
| OneDrive **SalCAPA Intake - Governed- DO NOT USE** | Candidate for deletion | Delete only after confirming its single acceptance artifact is duplicated or no longer required and the live binding still points elsewhere |
| `PersonalCacheLibrary` | Do not delete | Microsoft-managed content outside this cleanup |
| SharePoint **DPSDocsAndPersonnel** | Do not delete | Outside the verified SalCAPA scope; requires a separate owner and retention review |

## Migration and deletion gates

No site or folder should be deleted until all of the following are true:

1. Exported inventory records item ID, path, size, modified date, owner, version/eTag, and hash where obtainable.
2. Each item has a disposition: migrate, retain in place, archive, reject, or delete.
3. Destination copy has been reconciled against source content and provenance.
4. SalCAPA intake binding and production acceptance confirm no runtime dependency on the candidate location.
5. Required retention, legal, contractual, and Protected Member obligations have been reviewed by an authorized person.
6. A named owner approves the deletion and a recoverability window is documented.

## Recommended implementation sequence

1. Approve this architecture and naming convention.
2. Create the target folders and metadata in **Salus Knowledge Sources**.
3. Create the restricted **Protected Member Records** and **System Governance** libraries.
4. Configure least-privilege access separately for SalCAPA, ChatGPT, Salus reviewers, and Protected Member users.
5. Pilot 25 or fewer representative documents across every supported format and classification.
6. Validate capture, provenance, human review, search/index isolation, version-change handling, and retrieval quality.
7. Inventory and migrate the existing SalCAPA Documents library and upload-staging tree in bounded batches.
8. Reconcile duplicates and superseded versions; preserve decision logs.
9. Complete end-to-end SharePoint/OneDrive report delivery acceptance.
10. Present an exact deletion list for human approval, then delete only approved candidates.

## Immediate deletion guidance

Delete nothing yet. The only location presently identified as a likely deletion candidate is:

**OneDrive → SalCAPA Intake - Governed- DO NOT USE**

It should not be deleted until its acceptance file has been checked against governance/acceptance records and the production binding has been re-verified immediately before deletion. All other named locations require retention or migration work first.
