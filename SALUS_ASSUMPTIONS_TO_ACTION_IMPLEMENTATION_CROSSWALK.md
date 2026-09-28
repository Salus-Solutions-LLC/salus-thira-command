# SAL-D055 implementation and report impact crosswalk

**Status:** Approved implementation requirements and exact-version inventory, 28 September 2026. **Handling:** Salus Internal Confidential. **Authority:** Program Charter, SAL-D055, approved product standards, SAL-D027/SAL-D043, approved Protection Advisor example, and current governed records. This crosswalk differentiates approved method, local candidate template, live implementation and issued Protected Member report.

## 1. Coverage and rule

The assumption → analysis → specific recommendation → paired narrative/checklist method applies where a Salus work product makes a material decision or recommendation. It does not require an anonymous questionnaire answer, a raw source record, a price estimate or an urgent field instruction to masquerade as a completed four-product assessment. Every applicable product uses stable IDs and reconciles the same evidence and authorization state. Search and impact-review current artifacts before each release; the inventory below is a bounded 28 September 2026 set, not a claim that every historical report has been revised.

| Surface | Required change | Current status and release gate |
|---|---|---|
| Program Charter, Decision Register, three-level framework and four product standards | Require testable working assumptions, alternatives and specific narrative/checklist recommendations at Levels 1–3. | Approved enterprise-method text under SAL-D055 after governed merge; no deployment implied. |
| SalINTEL™ controlled Word template | Add narrative + checklist where source-bound findings become same-level recommendations; link contradiction and validation request. | Local v2 candidate; prior approved v1 remains authority until exact revision, full-page QA, hash registration and human release. |
| SalTHIRA™ controlled Word template | Put concise narrative + checklist under analyst review, linked to BLUF rankings and six steps. | Local v2 candidate; prior approved v1 remains authority pending exact revision gate. |
| SalOPS™ working Word template | Pair each material option narrative with checklist and explicit proposed/authorized state. | Local v2 candidate; prior draft remains design reference pending template control. |
| SalCAPA™ working Word template | Reconcile source reports into one Member decision narrative and master checklist. | Local v2 candidate; prior draft remains design reference pending template control. |
| Protection Advisor Part 1 | Reuse existing brief questions; add answer-dependent educational conditional wording, an alternative/uncertainty and a voluntary Level 1 next step without raising question count or declaring a finding. | Approved design requirement. Exact live questionnaire, result copy, print/PDF and privacy/functional tests remain separately gated. |
| Protection Advisor Part 2 | Within authenticated consent, ask at most a bounded decision concern and desired outcome/decision role only when existing fields do not already supply them; show a preliminary answer → possible implication → Level 1 validation question → optional Member action. | Approved design requirement. Do not request sensitive person-level material or required document upload. Exact deployed version and approved example must be inspected before code/output change. |
| Active/working Tierra Linda Level 1 SalINTEL™, SalTHIRA™, SalOPS™ and SalCAPA™ documents | Reconcile actual evidence and report lineage; write Member-specific assumptions and paired recommendations; preserve one report identity and current working/issued status. | SAL-D027 impact open. Do not insert generic template prompts as findings or imply issue/release. |
| Issued Member reports, specialist outputs and future sectors | Apply materiality and version review; amend current governed record if the new rule changes a decision, action, reader understanding or required proof. | Inventory per engagement and human release required; no blanket retroactive overwrite. |
| SalCAPA™ dashboard and records | Store source/assumption/recommendation/checklist/decision/proof links and distinct action states; show next review and contradiction without revealing restricted method. | Design requirement only, not a deployed dashboard feature. |
| Proposals, pricing and marketing | Describe the value of specific analyst judgment and actionable outputs at the purchased level; scope analyst time, reviewer, source limits and validation. | Human-reviewed copy/price change required. Do not claim universal superiority to all competing methods. |

## 2. Exact local Word candidate inventory and initial QA

Candidates are additive, member-neutral revisions in the shared local workspace under `work/assumptions_to_action/`. No Protected Member data was added. Microsoft Word exported each candidate to PDF on 28 September 2026. The exported PDFs rendered to page images and contact sheets; page 2 had zero extractable text in each. Existing page counts were retained: SalINTEL™ 9, SalTHIRA™ 6, SalOPS™ 6 and SalCAPA™ 6. Visual review checked the inserted narrative/checklist section, page flow, blank second page and `page X of Y` treatment. These are **candidates**, not newly approved binary authorities or delivered Member reports.

| Candidate DOCX | SHA-256 | Rendered pages |
|---|---|---|
| `SalINTEL Report Template v2 CANDIDATE.docx` | `4EAA32BA36B5BD6C597CDD45E73FF98989462A90BE8C1D970B556ED357348A08` | 9 |
| `SalTHIRA Report Template v2 CANDIDATE.docx` | `56119F4EB7FB6FD4CE97D07CF27600C41F60F58CB43ED62F4BEEC73BDC976AB6` | 6 |
| `SalOPS Report Template v2 CANDIDATE.docx` | `688C3BC453AFBFB207E605A764C9C5BEB88CA090ED6776A1834CCF4FD4137BBD` | 6 |
| `SalCAPA Integrated Report Template v2 CANDIDATE.docx` | `D1BA8F2DF6CB3D824CB30FA389A1145E9F81D8DA7E0C050F05E8F87D83038E00` | 6 |

Before a candidate replaces an approved template or is used to issue a Member report, inspect every page at full size, verify typography/accessibility/internal links and PDF/print parity, approve the exact binary and storage/access location, register its hash and supersession, and complete report-specific SAL-D043 conformance. A PDF text check alone does not prove a visually blank page; the page image review is also required. Do not overwrite the approved v1 binaries or create a duplicate report to force adoption.

## 3. Protection Advisor exact-answer design

Do not add a question to anonymous Part 1. Version an answer-rule crosswalk for the existing `decision_authority`, `leadership_record`, `ownership`, `reporting`, `warning_thresholds`, `required_actions`, `integrated_test`, `training_test`, `degraded_communications`, `investment_tradeoffs` and `priority_gaps` keys. For an applicable answer, write:

> “Your answer may indicate [plain-language operating concern]. It can also reflect [benign alternative or missing information]. A Level 1 assessment can check [specific record or safe test] and identify whether [decision/action] would help. You may request a Level 1 scope; this preliminary result does not establish a control failure.”

Part 2 may ask, only if absent from current consented fields: “Which decision would you most like a Level 1 assessment to help you make?” with bounded non-sensitive categories and “not sure / prefer to discuss”; and “Which role or governing group can approve the next step?” Do not collect a person's suspected behavior, gate/access specifics, medical details or credentials in free text. The report can present an optional **Member next-step checklist**, not a formal SalOPS work order: ☐ choose the decision owner; ☐ identify a non-sensitive existing record; ☐ request a Level 1 scope if desired. Urgent safety guidance remains available without purchase.

## 4. Controlled rollout and acceptance

1. Review this method and four template candidates against current approved artifacts and exact live Protection Advisor questionnaire/report versions. Preserve earlier report identities, answer keys and consent.
2. Approve exact Advisor wording and template binary revisions; run functional/privacy checks, anonymous/authenticated boundary checks and required rendered DOCX/PDF/print parity.
3. Perform SAL-D027 materiality impact on each active or issued report. For material Member-specific revisions, confirm sources, assumptions, contradictions and authorizations before writing the narrative and checklist in the existing governed report lineage.
4. Add stable ID and lifecycle fields to SalCAPA only through normal software change/release controls. Verify live behavior after immutable release and retain rollback.
5. At each issue, a qualified analyst and authorized human reviewer confirm source-to-assumption-to-recommendation trace, causal and alternative analysis, checklist specificity, narrative/checklist agreement and action-state accuracy.

Unfinished implementation remains visible in the current handoff. Method approval, local template candidates and a passed render check are not evidence that all questionnaires, reports, dashboard features or prior Member findings have been updated.
