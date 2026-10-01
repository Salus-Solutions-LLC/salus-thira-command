# Protection Advisor Part 2 — controlled review candidate

**Status:** Unapproved source and Word review copy, 01 October 2026. No live publication.

- Source questionnaire version: `SPA-PUBLIC-QUESTIONNAIRE-2.3.0`. Part 1 retains nine anonymous common questions. After account consent, Part 2 carries those answers forward and asks the other 19 common questions. Previously started 2.2.0 sessions keep the prior 28-question wording.
- The 28 common question mappings cover the 32 core capabilities and five mission areas. The Part 2 profile also records the proposed covered operation and decision boundary; reported answers do not establish readiness or compliance.
- Local Word review copy: `proposals/qa/questionnaire_candidates/Protection Advisor Part 2 Questionnaire.docx`; SHA-256 `925D68A4CBB52CDB2AD37455FBC71732E41B595D8C827FAA365AE578AB93A353`.
- Native Microsoft Word exported nine pages on 01 October 2026. All pages were visually inspected; page 2 is blank and footers follow `page X of 9`. The final package-path explanation starts with its heading on page 9. The Word theme-font override was removed, and extracted visible text uses Arial headings and Times New Roman body; symbol glyphs use Segoe UI Symbol.
- Font and final-page repair: `proposals/qa/normalize_questionnaire_fonts.py`; export audit: `proposals/qa/audit_native_word_exports.py`.
- Source builder: `proposals/qa/extend_part2_questionnaire.py`. The Word binary and renders are local review material, not an approved binary template or issued Member document.

**Release gates:** Exact-head application/contract CI, anonymous-to-consented and legacy-session browser testing, accessibility review, nonexpert comprehension review, exact version approval and governed Azure/Wix release. The production package route stays locked until the complete release record passes.
