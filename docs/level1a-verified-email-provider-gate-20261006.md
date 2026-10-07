# Level 1A buyer email-verification release gate

**Status:** Member-neutral QA design candidate for exact-source and qualified security review. This document does not change application code, Azure settings, credentials, public sign-in, payment or uploads. **Date:** 6 October 2026.

## Authority and current baseline

Apply the Program Charter, SAL-D091, SAL-D101 and SAL-D102, the approved Level 1A rev10 Word template (SHA-256 `63AD42DADC81A054FA28EF55EAADC8DFBD10C9CA983AB81C2D085E033F046CF6`), the approved public-buyer identity design, and the current protected release record. The accepted Advisor app is v3.218, protected run `37496191059`, image `sha256:528d4c475aa2540fbdbed998a066aca00ee800a2fc61ab351a8c9c82882f6887`, with v3.217 retained for rollback. Customer sign-in and Level 1A purchase controls are off; checkout, receipt, intake and Member uploads are closed.

The v3.218 `customer_oidc_callback` validates the signed ID token, pinned issuer/audience/tenant, state, nonce and subject, then requires nonempty `email` and boolean `email_verified=true` before binding a buyer. No downstream action may relax those checks to make a test pass.

## Observed provider behavior and boundary

Marc privately completed one email-code sign-up using Salus-controlled `Contact@Salus.Solutions` in the `SalusLevel1ABuyer` flow through a temporary, isolated test app. With the same `openid profile email` scopes used by SalCAPA, the signed test-app ID token contained an email and `idp=mail`, but contained neither `email_verified` nor `verified_primary_email`. A first `openid`-only token lacked email and is not a scope-parity test. Record claim presence only; do not retain or publish either token, code, subject or email value. This result predicts a fail-closed response from the current callback but is **not** acceptance of the production confidential client or its authorization-code exchange.

The test app was removed from the flow and deleted. A refreshed External ID app list showed the original two registrations, including unchanged `Salus Level 1A Buyer Access`. No production identity setting or Member control changed.

Microsoft documents the local External ID email one-time-passcode method as sending a code at sign-up and at each sign-in. Its optional-claims reference describes `verified_primary_email` as sourced from `PrimaryAuthoritativeEmail`. Those documents do not prove that this Salus app emits the optional claim or that an ordinary `email` claim equals it:
- https://learn.microsoft.com/en-us/entra/external-id/customers/concept-authentication-methods-customers
- https://learn.microsoft.com/en-us/entra/identity-platform/optional-claims-reference

## Proposed smallest safe experiment

1. A qualified reviewer checks the exact proposed Azure app-registration change and code predicate before either is applied. Keep the production customer sign-in, purchase and upload switches off. Record current app settings and a rollback path.
2. Request **only** the `verified_primary_email` optional ID-token claim on the existing confidential buyer app. Do not add a broad API permission, redirect, credential, identity provider or public entry point. Read back the exact setting.
3. Run one fictional authorization-code sign-in through the production callback with `Contact@Salus.Solutions`; Marc enters any Microsoft code privately. Collect safe claim-presence and pass/fail markers, never a raw token or code. Require a signed token with the pinned issuer, audience, tenant, state and nonce and a nonempty pairwise subject.
4. Accept a verified address only if the provider actually emits a nonempty authoritative verified-primary-email claim and it exactly matches the normalized `email` used for the buyer record. Absence, different values, malformed values, unsupported sign-in methods, provider errors and claim ambiguity must fail closed. Do not use `idp=mail`, `preferred_username` or plain `email` alone as verification evidence.
5. Prove one buyer maps to one isolated application tenant; repeat callback, changed email, replayed/expired state, wrong issuer/audience/tenant, missing nonce and cross-tenant access are denied without duplicate tenant, order, charge or receipt. Existing workforce identity remains separate.
6. If the optional claim is absent or its semantics cannot be qualified in the real authorization-code flow, revert the app-registration change and keep the public switch off. Review an alternate provider-authoritative method; do not lower the security predicate.

## Downstream release gates

A passing identity check would authorize **only** the next controlled acceptance work. It does not publish Level 1A. Prove signed Stripe sandbox Checkout and webhook, paid-before-intake status, exact approved buyer-specific rev10 Word issuance and electronic acceptance, immutable receipt, scanner-held clean/adverse exact Blob versions and real failure-alert delivery/recovery. Verify tax and fixed $1,500 scope under SAL-D102. Review live Member wording, phone, Word and print output. Keep paid order and file access gated until all exact-source, Azure preview, cost, security, rollback and qualified-output determinations are recorded.

**Owners:** Engineering prepares the test and evidence; Marc is the named qualified reviewer for the security design, exact protected source and live output. This draft seeks no approval to open public controls. Preserve stopped Tierra Linda, Protected Member isolation and paused large-batch issue #520.
