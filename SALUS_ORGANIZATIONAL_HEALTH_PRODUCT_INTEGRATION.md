# Organizational-health integration across Salus and Protection Advisor

**Status:** Approved member-neutral product and Protection Advisor integration design, 28 September 2026 (SAL-D052). This record does not change the deployed questionnaire, scoring, retained submission, report binary or operational authority.  
**Handling:** Salus Internal Confidential. **Controlling authorities:** Program Charter, SAL-D051 and SAL-D052, four product standards, three-level framework and approved Protection Advisor example report.

## 1. Single evidence-to-decision chain

Use one stable finding chain, within the Protected Member boundary:

**Protection Advisor signal → Level 1 SalINTEL evidence and organizational-health domain → Level 1 SalTHIRA scenario, mission-area and capability effect → Level 1 SalOPS option and separate authorization → Level 1 SalCAPA Member decision, owner, proof and residual risk.**

The Protection Advisor result is educational preliminary information. A questionnaire answer is a lead, not a verified organizational-health rating, a misconduct allegation or proof of control failure. Preserve answer version, wording, consent, applicable profile data, report identity and limits. The complete twelve-domain assessment begins in SalINTEL at the authorized Level 1. Each later level validates a named decision-changing uncertainty.

## 2. Protection Advisor Parts 1 and 2

### Part 1 — anonymous, low burden

Keep the existing question count and anonymous boundary. Reuse the current question keys rather than create a long leadership inventory:
- `decision_authority`: introduce authority, delegation and succession.
- `leadership_record`: introduce how leaders know, decide, communicate and review.
- `ownership`: introduce accountable owner and review date.
- `reporting` and `warning_thresholds`: introduce upward information flow and pattern detection.
- `required_actions`, `integrated_test`, `training_test` and `degraded_communications`: introduce whether direction is understood and practiced under disruption.
- `investment_tradeoffs` and `priority_gaps`: introduce prioritization and governing tradeoffs.

Use plain-language educational feedback: “A written plan may not show whether people understand it or can use it when a leader is absent. A Level 1 assessment can check decision rights, handoffs and routine/stress performance.” Tailor the explanation to the answers. Say “not sure” and “prefer not to answer” are information limits, not poor performance. Do not derive a twelve-domain score from Part 1 or identify individual leaders.

### Part 2 — authenticated profile and decision context

Within the existing authenticated, consented record, collect only decision-useful, non-sensitive detail. Prefer bounded choices and role names to names of individuals:
1. **Governing form:** corporation, nonprofit, HOA/member association, public body, partnership, other/uncertain. This selects the applicable authority review; it is not a legal conclusion.
2. **Leadership and decision concern:** unclear authority; slow approvals; undocumented handoffs; rules not reaching people; limited reporting of problems; succession gap; no specific concern; unsure; prefer to discuss. Permit multiple selections.
3. **Evidence currently available:** governing instruments/delegations; organization chart; process or decision records; policies and distribution records; incident/exercise records; none/uncertain. Ask for availability, not upload into an intake text field.
4. **Decision owner for a Level 1 scope:** role or governing group, using the existing `decisionAuthority` field; personal name optional.
5. **Optional free text:** one recent *process* example, with explicit instruction not to enter names, allegations, access credentials, medical/financial account data or privileged material.

Avoid a compulsory multi-page governance survey, person-level accusations or a background-investigation prompt. SalINTEL's scoped collection plan later requests the actual documents, interviews and permissions.

### Protection Advisor results and reports

Add a short **Leadership, decisions and operating resilience** explanation in preliminary Part 1 results and a tailored Part 2 report section only when relevant. Show:
- what the answer indicates and what remains unverified;
- one existing strength or practice to preserve if the Member reported one;
- the practical daily-work and disruption question it raises;
- why Level 1 can help, including specific evidence to review;
- voluntary separate service options only when a qualified need exists.

Do not call a preliminary answer an observed gap, measured rating, legal violation or formal THIRA result. Keep the approved example report's substantive architecture, confidentiality, OPM style, accessibility and DOCX/PDF/print parity. Preserve same-record revisions and version history.

## 3. Four-product application

| Product | Required organizational-health use | Output and boundary |
|---|---|---|
| **SalINTEL™** | Explain and screen all twelve domains; map formal and actual authority; trace decisions, process and promulgation; preserve strengths, contradictions and unknowns; collect six-step SalTHIRA inputs. | A titled organizational-health section with domain evidence/confidence, routine/stress effects, missing information and next-level questions. Personal investigative leads stay restricted. |
| **SalTHIRA™** | In each of the existing six steps, examine how leadership, authority, information, culture and process change scenario consequence, capability targets, demonstrated capacity, gaps and treatment choices. | The BLUF and five-mission-area/core-capability analyses state the decision effect and confidence; no generic organization score substitutes for performance evidence. |
| **SalOPS™** | Compare no action and proportionate options; preserve strengths; specify lawful owner, resources, promulgation, training, daily/stress benefit, proof and retest. | Distinct proposed/offered/authorized/performed/verified states; services are optional, evidence-linked and separately scoped. |
| **SalCAPA™** | Reconcile exact same-level reports and any contradiction; show the Member's decision, authority, owner, funding, timing, evidence, residual exposure and retest. | One integrated decision summary and protected tracking record, without duplicate reports or automatic action. |

## 4. Level depth and collection burden

| Level | Decision value | Organizational-health proof |
|---|---|---|
| 1 | Identify material strengths, vulnerabilities, decisions and the evidence needed next. | Screen twelve domains using authorized available material; bounded interviews if in scope; a routine and stress hypothesis; confidence and unknowns. |
| 2 | Validate selected changes that could alter priorities or recommended options. | Review governing and operating records, interview roles, trace representative decisions and policy promulgation, conduct walkthroughs and specialist review. |
| 3 | Demonstrate and sustain approved complex changes. | Observe representative work, exercises, trend/denominator analysis, implementation evidence, retest and residual-risk review. |

The Member may stop after a useful Level 1 package. Level 2 follows a qualified Level 1 package and Level 3 follows a qualified Level 2 package. A level upgrade, investigation, operational service or service sale requires its own scope and authority.

## 5. Content crosswalk and acceptance gates

Use `SALUS_REQUIRED_INFORMATION_AND_LENS_CROSSWALK.md` to stage the Member packet and conditional proof requests after Level 1 authorization. It includes the other approved professional lenses as well as organizational health; Protection Advisor continues to collect only preliminary signals.

For every material leadership or process signal, maintain a controlled crosswalk:
`advisor question/answer/version → educational statement and caveat → SalINTEL domain/source/contradiction → SalTHIRA scenario/target/gap → SalOPS option/state → SalCAPA decision/owner/proof → report version and review`.

Before altering production Part 1/2 questions, rules or reports:
1. Inspect the exact current questionnaire, recommendation logic, retained-record schema, approved example DOCX/PDF and production report outputs.
2. Preserve the current Part 1 number or reduce burden; show completion-time and comprehension evidence. Add detail only to authenticated Part 2 where useful.
3. Verify that “not sure,” not applicable and declined responses do not automatically lower a performance rating or trigger a service pitch.
4. Validate organization-type applicability, branch logic, accessibility, privacy/consent, identical substantive meaning across web, DOCX, PDF and print, and existing-record revision rather than duplication.
5. Review a representative short, long, adverse and uncertain answer pattern with a human analyst. Confirm no unsupported person-level, legal, financial or capability finding.
6. Apply SAL-D027 report impact and SAL-D043 conformance, required OPM typography, confidentiality, blank-page and “page X of Y” controls where applicable. Record exact version, tests, reviewer, authorization and release.

## 6. Current-state boundary

The current repository questionnaire version inspected for this design is `SPA-PUBLIC-QUESTIONNAIRE-2.0.0` in `public_protection_advisor.py` on `development/salcapa-platform`, read 28 September 2026. Its existing Part 1 keys already cover authority, ownership, reporting and leader decisions; Part 2 already asks who can authorize the next step. This design supplies the method and approved question intent. It does not assert that the live site, scoring, protected results or downloadable reports have been changed. The approved Protection Advisor example report must be inspected directly before an exact report implementation and visual release.

## SAL-D055 assumption-to-action Advisor boundary

Under SAL-D061, use the existing short authority/reporting prompts to introduce one conditional question about whether concerns reach a competent decision maker and whether a critical function can continue during disruption. Do not add a long mandatory psychometric, personnel or near-miss questionnaire to Part 1. Authorized Level 1 SalINTEL™ can examine actual role handoffs, protected upward reporting, near-miss follow-through, informal helpers and stress decisions; Level 2/3 can validate selected performance. A favorable answer is a lead, not proof of culture or command effectiveness. See `SALUS_THOUGHT_LEADER_RECONCILIATION_20260928.md` for the bounded source challenge.

The Protection Advisor questionnaire introduces the distinction between a reported condition and a tested capability without adding a long mandatory survey. **Part 1:** use existing answers to phrase a short, conditional educational hypothesis (“Your answer may indicate ...; a Level 1 assessment would check ...”), state an alternative or uncertainty, and suggest one voluntary, proportionate next step. Do not turn an anonymous answer into an analyst finding or operational checklist. **Part 2:** authenticated, consented answers may select a decision concern, observable desired outcome, responsible role and whether a non-sensitive supporting record is available; use existing fields when possible. Do not require document uploads, names of suspected people or detailed vulnerability text in open intake. The preliminary report should show the answer, its limit, a specific Level 1 validation question and an optional first action the Member can consider. Formal working assumptions and narrative/checklist recommendations begin only after qualified, authorized SalINTEL™ and continue through the same-level product chain.

Before changing live Part 1/Part 2 questions, scoring, report copy or downloadable output, inspect the exact deployed version and approved example report, test completion burden and consent/privacy, preserve submission and report identity, and complete SAL-D027/SAL-D043 rendered and functional gates. Method approval alone does not deploy questionnaire changes.
