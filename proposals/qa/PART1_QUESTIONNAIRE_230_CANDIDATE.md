# Protection Advisor Part 1 — controlled review candidate

**Status:** Unapproved source and Word review copy, 01 October 2026. No live publication.

- Source questionnaire version: `SPA-PUBLIC-QUESTIONNAIRE-2.3.0`.
- Nine common questions; prior 2.2.0 sessions retain their 28 common questions. Applicable conditional questions still follow the common screen.
- The short screen records reported conditions and does not assign numerical ratings to the 32-capability framework or five mission areas. Unasked subjects remain unassessed.
- Local Word review copy: `proposals/qa/questionnaire_candidates/Protection Advisor Part 1 Questionnaire.docx`; SHA-256 `966125F8DD9B7C4011E3A4A1B42DA3D26261228F66908E469BCF4DBF143E8B2E`.
- Native Microsoft Word exported five pages on 01 October 2026. All five page images were visually inspected; page 2 is blank and page footers follow `page X of 5`. The Word theme-font override was removed, and extracted visible text uses Arial headings and Times New Roman body; symbol glyphs use Segoe UI Symbol. This checks the local candidate only.
- Font repair: `proposals/qa/normalize_questionnaire_fonts.py`; export audit: `proposals/qa/audit_native_word_exports.py`.
- Source builder: `proposals/qa/shorten_part1_questionnaire.py`. The Word binary and renders are local review material, not a governed approved template.

**Release gates:** Exact-head application and report CI; accessibility, signed-in browser/Member comprehension and legacy-session migration checks; exact versioned content acceptance and governed Azure/Wix release. Preserve the production package lock until the full release record passes.
