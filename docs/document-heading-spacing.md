# All-document heading spacing

SALUS-DOC-HEADING-SPACING-001 applies to every new or materially revised Salus document and reusable template: Heading 1 has 12 pt before and 12 pt after; Heading 2 has 12 pt before and 6 pt after. It overrides earlier conflicting spacing values only.

For Word generators, call `apply_heading_spacing(document)` from `salus_document_styles.py` immediately before saving a controlled successor. The helper changes only spacing, follows custom paragraph-style inheritance and outline levels, and includes nested tables and document stories. It does not approve the content, issued filename, branding, font sizes, accessibility or layout.

Run `python tools/verify_salus_document_heading_spacing.py path/to/exact.docx` before issue. The read-only check reports exact file hashes and effective spacing findings. Nonzero means a defect or unreadable file. Then render the exact final file in native Word where available and inspect every page under the existing standards; archive evidence outside the repository.

## Adoption and impact register

| Document route | Implementation or disposition | Remaining acceptance |
|---|---|---|
| Twelve-topic white paper v1.5 | Exact Word file checked; all 96 used headings match; 54-page native Word proof retained privately | Full research/Charter assurance is separately incomplete |
| Protection Advisor Word report and Word scope-receipt generators | Shared rule applied before save; generated-file smoke tests check output | Deployment and populated-document page review remain separate |
| Protection Advisor PDF report | H1/H2 paragraph styles set to 12/12 and 12/6 pt | Native output parity and exact populated-page review remain separate |
| Sequential package proposal generator | H1/H2 style values and shared pre-save application aligned | Any successor binary requires exact-file inspection before use |
| Four-product level/band template candidate builder | Preserves original source bytes; applies shared rule to a generated successor | Local source-path availability, each successor's page review and artifact registration remain required |
| Retained approved four-product Word templates, other active drafts and distributed/cloud copies | Previous approval does not waive new spacing; preserve originals and create controlled successors before next use | Complete current artifact inventory, original access and successor acceptance remain pending; no global migration claim |
| Other Word, PDF, presentation or print workflows | Standing all-document rule applies wherever level 1/2 headings occur | Verify actual authoring styles, override behavior and exact rendered output; record a justified nonapplicability if the heading levels do not occur |

This register is a bounded route inventory, not an exhaustive organization-wide document census. Historical proposal/QA scripts are not current approved production templates. No distributed original or customer-owned document is silently changed. A checked source merge is not deployment or publication.
