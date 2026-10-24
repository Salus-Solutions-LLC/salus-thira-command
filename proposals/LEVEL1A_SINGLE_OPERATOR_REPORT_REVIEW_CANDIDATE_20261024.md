# Level 1A single-operator report review candidate

Status: source candidate, not an approved release decision or deployed exception.

## Reason

Marc directed on 24 October 2026 that ChatGPT and Marc Duncan are the only people building SalCAPA. `Contact@Salus.Solutions` has no Microsoft Azure account, and Marc confirmed there is no second qualified Salus staff reviewer. The current paid-report route requires the QA evidence submitter and reviewer to have different authenticated user IDs. Creating a second login controlled by Marc would satisfy that check without providing independent human judgment and must not be represented as independent review.

## Proposed narrow path

1. Preserve the existing independent-review path as the default. A single-operator exception applies only to the paid Level 1A Assessment report pilot when protected configuration pins Marc's existing staff Microsoft email, Entra object ID, and one paid order ID. All three settings default to empty, so the exception is disabled. The configured identity and protected activation require separate readback and rollback.
2. ChatGPT may prepare working narrative, source crosswalks, contradictory hypotheses, automated checks and page-review prompts. Its output is a draft or challenge record, not a qualified human review.
3. Marc must personally inspect the exact source, every rendered Word/PDF page, accessibility/navigation and format parity. He records the SAL-D043 conformance matrix, unresolved limitations, qualifications, and an explicit self-review declaration for each exact report hash. The record must say `Single-operator human review by Marc Duncan`; it must not say `independent reviewer`.
4. The issue action remains a separate named human decision after source reconciliation and four exact-page reviews. Audit both actions, reject stale hashes and changed source, and preserve buyer isolation, one governed issue packet, and rollback. No automatic issue follows a successful check.
5. A real second qualified reviewer can be added later through the default independent path. Existing issued versions are not silently relabeled.

## Open engineering and acceptance work

- Current staff draft and QA archive uploads call inline `scan_bytes` and require `Clean`. Verify the protected scanner configuration and repair using a governed fail-closed file-screening path before accepting any staff DOCX/QA ZIP.
- Add tests for default denial of same-user review, exact configured-identity gating, no prototype/session shortcut, complete page evidence, hash/source changes, idempotency and buyer isolation. Record the solo mode in the review digest and issue snapshot so it cannot be mistaken for independent review.
- Obtain exact-source review of this candidate. Record an approved decision and Charter impact before protected activation. Complete a protected named-buyer pilot and separately govern public Wix/live payment release.

The four fictional Cedar Site reports are not yet populated or issued. Its approved source document was uploaded once and the buyer page showed `cleared`, but its six statements remain buyer-provided and unverified.
