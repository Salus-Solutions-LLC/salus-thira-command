# Level and band report template candidate contract

**Authority:** SAL-D088–SAL-D090. **Purpose:** Prepare four member-neutral title and opening-prompt candidates while retaining the exact registered Word references and all issued reports. These candidates do not supersede approved binary templates until governed visual, content, access and release review.

| Product | Retained reference in local `work/` | SHA-256 | Baseline sections / content |
|---|---|---|---|
| SalINTEL | `approved_templates/SalINTEL Report Template.docx` | `5A99C3F0A3DB126F101407617AABA7CB8EB098C3D704E436B01C5D8520BB1959` | 3 sections, 57 body paragraphs, 15 tables; registered 9 pages |
| SalTHIRA | `approved_templates/SalTHIRA Report Template.docx` | `29B896804C44B56D5A32BA377FE557B676649FAC88C83D674BE77EA088B81FF8` | 3 sections, 52 body paragraphs, 4 tables; registered 6 pages |
| SalOPS | `salops_design/SalOPS Report Template DRAFT.docx` | `4CE3DB45CA2C39BF28D278296D23CCEC322AC4E7738793D95B7170EC12170043` | 3 sections, 51 body paragraphs, 4 tables; draft |
| SalCAPA | `salcapa_report_design/SalCAPA Integrated Report Template DRAFT.docx` | `A1FAE0F2187C0B7DE74246DE70203B6F40F172434BC197127EF30E907153D3A1` | 3 sections, 54 body paragraphs, 9 tables; draft |

All four references use letter paper, three sections, a confidential cover and a blank second-page section. SalINTEL margins are 1 inch; the other three use 0.9 inch. Preserve every section, header/footer, table, image, field, relationship and paragraph outside the exact title, cover status/version and executive opening prompt. Existing title paragraph uses the Word `Title` style. Render review found that the references' font-theme selectors override their explicit Arial heading choice with Calibri. Candidate `word/styles.xml` removes only the theme font selector attributes so the intended Arial/Times New Roman roles render. All other package members must have the same uncompressed SHA-256 as their references.

**Editable slots:** title on cover; cover status/version sentence to mark candidate lineage; first executive/BLUF prompt to demand exact level/band, covered decision unit, exclusions and evidence status. All other bracketed instructions remain for later controlled template review. The proposed title uses `Level [path]`; before a Member issue the author replaces `[path]` with `1A Access`, `1A Standard`, `1B`, `1C`, `2A` etc. and replaces customer name. The exact front matter and executive summary must state the chosen path. A template is never an issued report.

**Fidelity gates:** reference hash, ZIP integrity, unaffected package-part hashes, section count, blank page 2, every nonblank page footer `page X of Y`, font check, all-page render and visual comparison. Any layout change outside the edited text, broken page, accessibility defect or unresolved placeholder in a proposed Member issue blocks promotion.
