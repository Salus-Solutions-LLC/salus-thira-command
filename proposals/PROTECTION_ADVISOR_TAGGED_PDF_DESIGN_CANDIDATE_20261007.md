# Protection Advisor tagged PDF design candidate

Date: 07-10-2026
Status: Candidate revision 2 for qualified design review. This revision corrects the production-route assumption in revision 1. It changes no runtime, image, Azure resource, or public control.

## Problem and observed evidence

A fictional Board PDF made by the direct ReportLab path has ten pages and /Lang en-US but no /StructTreeRoot or /MarkInfo. It has no tagged reading structure for headings, paragraphs, tables, or figures. PR #783 merged as b67e7e83dcf5c90971556b08ebf15ddd7aca4b5a and added alternative descriptions to the three cover graphics and two footer logos in generated Word reports. Frozen v3.226 predates that repair and has no published image.

Local Windows QA converted the repaired fictional Word report with LibreOffice Writer UseTaggedPDF=true. The output retained ten pages and has /Lang en-US, /StructTreeRoot, /MarkInfo /Marked true, heading/table/figure roles and three cover-figure descriptions. All ten pages were rendered in a contact sheet with the expected blank second page, blue headings, black body, watermark and footer. This proves a local candidate, not full accessibility, font fidelity, live route behavior or release acceptance.

## Existing governed PDF path that must be tested first

The current public report route in `public_protection_advisor.py` already renders the approved-template DOCX and calls `convert_member_docx_to_pdf` in `protection_advisor_member_reports.py` when the exact local Arial and Times font files are absent. That helper temporarily places the DOCX in the governed Microsoft 365 report folder, requests Graph `content?format=pdf`, validates the PDF envelope and size, removes the temporary DOCX, and stores the issued PDF separately under its report reference, revision, SHA-256 and size. The direct ReportLab route is selected only where those exact local font files are available. The Linux application image does not install them. PR #599 introduced this fallback and merged as 0716eb1f2bbc2916862bda83b28f01514aecf0ef.

Therefore no new converter or image package should be selected until a fictional PDF from the **actual Microsoft 365 conversion route** is inspected. Revision 1 of this design proposed LibreOffice in the application image before checking that existing path; that proposal is superseded by this section.

## Acceptance and implementation sequence

1. Obtain a fictional current Board report through the existing governed Microsoft 365 conversion path. Confirm the exact source Word template and repaired generator, document identity, stored SHA-256, page count, font substitution/embedding, blank second page, layout and complete substantive content. Do not read or disclose another Protected Member's report.
2. Inspect the returned PDF for /Lang, /StructTreeRoot, /MarkInfo, heading and table roles, figure descriptions and reading order. Render and review every page and compare it with the exact Word original and print output. An automated structure check alone cannot certify accessibility.
3. If the current path yields an acceptable tagged PDF, add fail-closed output validation and exact-version regression evidence to that path. Preserve its temporary-file cleanup, storage identity, authorization and immutable snapshot controls.
4. If it does not, prototype the smallest approved change to the existing Microsoft 365 conversion path. Only if that path cannot meet the report standard should the local LibreOffice candidate be reconsidered. A local candidate requires pinned Linux package, licensed font source and exact font proof, image-size/cold-start and cost check, no-network/least-privilege execution, bounded time/memory/output, concurrency and cleanup tests, and a separate reviewed source and Azure release.
5. No public route may silently fall back to an untagged PDF. The one-page scope receipt has its own source and accessibility acceptance; the Board report result does not clear it.

## Release boundary

Qualified reviewers must inspect exact Word and PDF outputs, table navigation, figure handling, contrast, reading order and every rendered page. Source tests, protected image publication, Azure preview/deployment, live report download, and final output acceptance are separate gates. Retain accepted v3.223 for rollback. Keep Level 1A buyer sign-in, checkout, payment, receipt, intake and uploads closed pending their own live evidence.

Owner: Salus engineering for isolated fictional test and evidence; Marc Duncan or named qualified reviewer for exact design, source and output determinations.
