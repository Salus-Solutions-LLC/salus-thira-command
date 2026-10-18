# Paid Level 1A Assessment report binding

Status: local implementation candidate; not an approval, release, or buyer report.

## Release boundary

The paid Level 1A buyer flow records its own order, quote, accepted issued
agreement, signed Stripe payment, immutable receipt, assessment, records
request, disclosure authority, and exact-version scanner decisions. The
four-report workflow currently uses separate package quote and acceptance
records and a different payment receipt. The production package-commercial
gate is closed. Those records cannot be treated as interchangeable.

The paid buyer must resume the existing order and provide records under its
verified payment. Salus staff must prepare SalINTEL, SalTHIRA, SalOPS, and
SalCAPA drafts from the same bounded assessment and qualified evidence.
Independent review, source reconciliation, page-by-page rendered QA, a named
issue authority, exact recipient delivery, and acknowledgment remain required.

## Source binding

Introduce an explicit, immutable paid-report source record. It must contain
the tenant, buyer, order, assessment, accepted quote and agreement IDs and
hashes, verified receipt hash, and the assessment boundary hash. On every
report read or write, recheck those fields against the current signed payment
ledger, stored receipt bytes, assessment link, and latest order version. A
payment hold, refund, changed scope, altered agreement or receipt, missing
assessment link, or wrong tenant/buyer blocks the action.

The report source must retain the **real paid Level 1A quote and acceptance**.
It must not create a fictitious package quote, staff approval, signer review,
or second payment. Existing package-commercial endpoints stay closed in
production. Report APIs require a separate report-only gate and explicit
assigned Salus staff or exact signed buyer authority.

## Report records and issue

Report versions refer to the paid-report source and retain original DOCX
bytes, SHA-256, method and template versions, title, status, and supersession.
Each version needs an exact rendered PDF and every-page inspection record;
accessibility, native Word, and format parity checks; the Charter conformance
matrix; independent qualified reviewer decision; and source references. The
SalCAPA report compares its exact current three product inputs and records
unresolved differences as blockers.

Issue is a separate append-only event by a named Salus authority. It checks
the four exact current reviewed versions, immutable paid source, recipient,
and comparison in one transaction. Delivery allows only the exact buyer to
retrieve the issued packet, records each download, and requires four-product
download proof before acknowledgment. No draft or unreviewed report is
buyer-visible. A correction creates a superseding version and issue; it does
not overwrite an issued record.

The candidate implements these report records and endpoints behind the real
paid-order checks. It keeps the existing package-commercial routes closed.
The fictional integrated test exercises a paid order, intake source binding,
four screened Word drafts, rendered PDF/page evidence, Charter matrices,
independent signed reviewers, SalCAPA comparison, human issue decision,
buyer isolation, Word/PDF download, acknowledgment and refund reclosure.
Those test documents are fictional and do not qualify real reports. Production
content, page-by-page review and qualified issue authority must be supplied
and verified before a public release decision.

## Required acceptance

1. Recover existing paid sandbox order L1A-10 in a fresh buyer session,
   without another checkout.
2. Prove one exact paid buyer's records request, disclosure authority, Clean
   and EICAR upload decisions, and absence of cross-buyer access.
3. Prove changed scope/agreement, payment hold/refund, altered receipt,
   missing scan, duplicate action, and wrong tenant or buyer fail closed.
4. Review all four fictional DOCX/PDF outputs in the approved method and OPM
   style, including blank second page, page numbering, accessibility, and
   source reconciliation. Obtain qualified analyst and issue-authority review.
5. Verify exact immutable image and guarded deployment with rollback. Public
   live payment, intake, upload, scanner, and report delivery require their
   own accepted release decision. Large-batch issue #520 and Tierra Linda
   remain paused.
