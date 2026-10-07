# Protection Advisor tagged PDF design candidate

Date: 07-10-2026
Status: Candidate for qualified design review. No runtime, image, Azure, or public control change is authorized by this record.

## Problem and observed evidence

The fictional Board report PDF made by the current ReportLab path has 10 pages and /Lang en-US, but no /StructTreeRoot or /MarkInfo. It therefore has no tagged reading structure for headings, paragraphs, tables, or figures. The approved Word template and generated Word report are the visual authority. PR #783 merged as b67e7e83dcf5c90971556b08ebf15ddd7aca4b5a and added alternative descriptions to five Word graphics; it did not change the direct PDF generator.

An isolated Windows QA conversion of that repaired fictional Word report with LibreOffice Writer PDF export and UseTaggedPDF=true produced 10 pages, /Lang en-US, /StructTreeRoot, and /MarkInfo /Marked true. The structure contains heading, paragraph, table, table-row, header-cell, data-cell, and figure roles. Three cover figures have alternative descriptions. A 72 dpi contact sheet of all ten pages shows the expected blank second page, report sections, blue headings, black body, watermark, and footer. This is a prototype result, not accessibility certification or live acceptance. Footer-logo semantics and reading order require independent review.

## Proposed implementation boundary

1. Render the Board report DOCX from the approved template and the same governed Part 1 and Part 2 objects. Preserve the existing report reference, handling label, audit lineage, authorization, and review state.
2. Convert only that local DOCX to a tagged PDF with a pinned LibreOffice Writer version in the immutable application image. Run the conversion as the unprivileged application user, with no network and a private per-request working directory. Pass arguments without a shell. Bound time, memory, input size, page count, and output size; fail closed on conversion or validation error.
3. Check that the result has the expected page count, blank page 2, /Lang, /StructTreeRoot, /MarkInfo, required heading and table roles, and alternative descriptions. These machine checks are screening gates. A qualified reviewer must inspect reading order, table navigation, contrast, every rendered page, and substantive DOCX/PDF/print parity.
4. Keep the current ReportLab path only as a comparison fixture during migration. Never silently fall back to an untagged PDF in the public download path.
5. Treat the one-page scope receipt as a separate PDF route requiring its own accessible source and acceptance. The Board-report change alone does not clear that gate.

## Before release

- Confirm the exact LibreOffice package version, license, image-size and cold-start effects, Azure preview, and expected incremental cost before adding it to the protected image.
- Build a fictional report in the same Linux image and compare every page and section to the approved Word report. Exercise malicious input, conversion timeout, missing fonts, partial files, concurrent requests, and cleanup.
- Run automated structure checks plus independent assistive-technology review. Record qualified review of the exact Word and PDF outputs.
- Preserve the accepted v3.223 rollback. Freeze a successor release only after source, accessibility, security, cost, and container tests pass. Image publication, Azure deployment, live download verification, and final acceptance remain separate governed gates.
- Keep Level 1A buyer sign-in, checkout, payment, receipt, intake, and upload controls closed pending their own live acceptance.

Owner: Salus implementation team for candidate and tests; Marc Duncan for qualified exact-design/source/output determinations under the Program Charter.
