# Package quote and authorization contract

**Status:** implementation contract for review, 29 September 2026. **Authority:** Salus Program Charter SAL-D080–SAL-D090. **Handling:** Salus Internal Confidential. This document does not authorize a price, engagement, report issue, or production deployment.

## Why this workflow is needed

The Protection Advisor can suggest a Level 1 band and give a draft scope receipt. The current SalCAPA assessment record stores a **requested** level, band, Access/Standard option and covered operation. These fields do not prove eligibility, establish a fixed quote, authorize work, qualify a predecessor or release any of the four reports. The next implementation must make those distinctions visible and enforce them in the API, not only in the page copy.

## One package identity and states

One governed package identity binds the Protected Member and tenant, decision owner, covered and excluded units, level, band, Access/Standard option, source Protection Advisor submission and receipt version, written scope version, quote version, agreement version, four report IDs and the predecessor package. Preserve immutable prior versions; a changed scope gets a new version of the **same** package, not another Member submission or duplicate report.

| State | Meaning | Permitted next action |
|---|---|---|
| Requested | Member or Salus named a possible path | Scope review; no paid work |
| Scoped | Salus named boundaries, exclusions, required evidence, deliverables and estimated effort | Eligibility and capacity review |
| Quoted | Authorized Salus commercial reviewer approved one fixed fee, assumptions, taxes if applicable, separate-service exclusions and validity period | Member accepts or requests change |
| Authorized | Authorized Member decision owner accepted the exact quote, terms, handling, transfer method and schedule; Salus accepted capacity | Secure intake and assessment work |
| In progress | Work is underway within the authorized boundary | Analyst and evidence review |
| Ready for release | Four exact report versions passed source, method, privacy, style, accessibility and qualified review gates | Human issue decision |
| Issued | Four separately identified reports and SalCAPA summary were released to the approved recipients | Decision tracking and reassessment |
| Superseded or declined | Prior quote/scope replaced or Member declined | Preserve audit record; no silent restart |

## Transition rules

1. Level 1 is the first paid package. Level 2 authorization requires a qualified issued Level 1 predecessor covering the same decision unit or an explicitly reviewed changed boundary. Level 3 requires qualified issued Level 2. A report filename, title, score, or requested state is not predecessor proof.
2. Band A means one combined decision unit. Band B requires distinct findings and a comparison for two named units or operations. Band C requires group-level priorities. Address count, revenue and headcount are scoping clues, not automatic band decisions.
3. Level 1A Access uses $1,500 only after Salus checks the simple eligible boundary and capacity. Level 1A Standard and every other level/band have no public fixed price until approved. The quote stores the exact amount, currency, scope assumptions, dates, owner and expiry. Separate SalOPS services receive separate scope and authorization.
4. Any change to covered units, report deliverables, price, dates or Member handling after quote must produce a new quote version and a fresh acceptance. The old authorization cannot silently cover new work.
5. Secure transfer starts after authorization. Request a short first packet and record missing material as missing; do not require personal directories or sensitive individual records by default.
6. Report generation may remain draft during work, but issue and distribution require exact-version human approval. The SalCAPA summary links the four approved report IDs and tells the Member which options are included recommendations and which are separately proposed services.

## Required implementation evidence

- Tenant-scoped tables or governed records for scope versions, commercial approval, Member acceptance, predecessor qualification, four-report links, and status events. Include actor, role, timestamp, source/decision basis and content hash. Use idempotency keys for accept/retry operations.
- API guards for every transition, including role and tenant checks, stale-version rejection, contradictory scope rejection, conditional Access eligibility, predecessor validation and separate SalOPS authorization.
- Plain-language views that show **possible path**, **fixed quote**, **authorized package**, **work status** and **issued reports** as different states. Show the exact covered unit, exclusions, fee, dates, Member action and what Salus will provide.
- Tests for A/B/C boundaries, declined or expired quotes, changed scope, repeated acceptance, cross-tenant access, missing predecessor, older issued versions, missing source receipt, and four-report release blocking. Verify existing governed submissions and reports are not duplicated by migration or retry.
- Reviewed database migration, backup and rollback; protected storage and retention review; native Word/PDF/print parity; accessibility; Azure and Wix end-to-end checks under governed release. Record actual image version and observed deployment before claiming live acceptance.

## Candidate implementation and remaining gates

The draft branch now has tenant-scoped, versioned Level 1 package quotes and exact-version Member acceptance records bound to the existing assessment. A Salus director or administrator records the written boundary, exclusions, fee, dates, agreement reference/hash, capacity and Access eligibility basis. Eligible Level 1A Access is constrained to $1,500; other package fees still require commercial approval. A signed-in Client Executive accepts the exact quote and agreement hashes using an idempotency key. The API rejects altered, expired or superseded quotes, cross-tenant reads and requoting after acceptance. Portable backup includes both records. Local tests cover the bounded path; this is a draft candidate, not a deployed or approved selling workflow.

The candidate does **not** yet bind the Protection Advisor receipt to a verified governed prospect identity, deliver and verify the actual agreement artifact to the Member, prove the Client Executive's legal authority outside the role mapping, handle amendments/declines, authorize Level 2/3 against qualified issued predecessors, connect all four exact report identities to package issue, or create a buyer-facing quote/acceptance view. The current API fails closed for Level 2/3 quoting and for requoting an authorized assessment. Engineering owns these gates and a reviewed migration/rollback; the product/commercial owner must approve eligibility and non-Access prices; qualified reviewers and Marc control protected issue and promotion. No production state should be inferred from this contract.
