# Level 1A public buyer identity: pre-code QA contract

**Status:** Design candidate for independent security, privacy, commercial and release review. No identity provider, public signup, Member permission, purchase flag or Azure resource is activated by this document. Issue #721 is the release blocker.

## Commissioned outcome and current failure

A previously unknown customer must be able to buy one bounded Level 1A Access unit for $1,500 without per-order Salus approval, accept the exact approved agreement online, prepay through a scope-bound Stripe Checkout, receive an immutable receipt, and submit files that remain held until a verified scan decision. The current production OIDC callback rejects an unprovisioned user while `SALUS_OIDC_AUTO_PROVISION=0`; `_level1a_draft_authority` requires an active Client Executive in an existing Protected Member tenant. Enabling order flags alone cannot satisfy the outcome. Keep them off until the full journey is accepted.

## Candidate boundary

1. Keep the existing Salus workforce OIDC issuer, preauthorized users, role mapping, sessions and Member tenants unchanged. Do not turn on its shared-tenant auto-provisioning.
2. Evaluate a separate customer identity tenant with a Microsoft-hosted signup/sign-in user flow, email verification and OIDC authorization-code exchange. The application must validate the exact customer issuer, audience, nonce, state, token signature and expiry independently of workforce OIDC. Do not accept a browser-supplied tenant or role.
3. On first verified customer sign-in, atomically bind the immutable `(issuer, subject)` to one new application tenant and one buyer identity with only the order authority needed for that tenant. Repeated callbacks and retries return the same binding. A user already bound elsewhere must never be rebound by changed email, company name or browser input.
4. A verified email proves mailbox control, not organizational contracting authority. Record the buyer's legal name and affirmative authority attestation with timestamp, agreement version, exact order scope and request identity. Show this in the agreement and receipt record. A second worker at the same organization requires a separate, authorized invitation path; matching an email domain grants nothing.
5. Bind draft, agreement, quote/amount/tax determination, Stripe Session, webhook, receipt and held-file records to the immutable application tenant, buyer and scope digest. A scope or tax change invalidates the prior agreement and Checkout identity. Duplicate webhooks and interrupted signup/payment must be idempotent.
6. Keep the public switch off until the customer provider, cost, exact-source review, protected deployment, fictional buyer acceptance, existing Member regression, scanner and Stripe acceptance, and qualified live-output review are recorded. Rollback restores the prior image and closes buyer entry without losing paid records.

## Existing Advisor account is not a shortcut

The Protection Advisor Part 2 account currently creates a 30-day account cookie before email verification and its login is tied to a resumable Part 2 assessment. Its password/session contract was built for Advisor save/resume, not Member contract authority or payment. Reusing that cookie as a Client Executive credential would cross a security boundary. It may supply a consented Advisor handoff after independent buyer authentication; it does not itself provision a Member.

## Independent review and provider checks before code

- Security reviewer checks token validation, account recovery, duplicate signup, unauthorized tenant binding, session expiry, CSRF, callback replay, rate limits and a stolen/changed-email scenario.
- Privacy reviewer checks minimum required identity data, source/consent record, separation of Advisor and Member data, retention under the existing published notice and deletion/records obligations. No new cookie or retention policy is implied.
- Commercial reviewer checks $1,500 one-unit boundary, no per-order Salus approval, approved rev10 agreement, prepayment and tax rules. Unsupported jurisdictions fail closed before charging; Texas standard consulting follows the recorded zero-tax determination unless scope changes.
- Engineering confirms that the exact Salus account can create and operate the separate customer tenant, email sign-in method, region, tenant/app registration, redirect URI, monitoring and rollback. Record actual contract price and any premium add-on or email delivery charge before resource creation. A public free tier is not proof of a Salus cost.
- Qualified reviewer signs this contract and any material design change before implementation.

## Acceptance cases traced to the outcome

| Case | Required result |
| --- | --- |
| Previously unknown fictional buyer signs up and verifies email | One new isolated tenant and buyer binding; no Salus staff or other Member role |
| Same callback, retry or duplicate signup | Exactly one binding, order and authority record; no second tenant or charge |
| Existing fictional Member signs in | Existing tenant, role and records unchanged |
| Other buyer, altered tenant ID, matching domain, changed email or stolen callback | Cross-tenant read/write denied; no role elevation or reassignment |
| Buyer abandons/retries before payment | Recoverable unpaid draft; no active assessment or file release |
| Buyer attests authority and accepts rev10 | Exact scope/version/price/tax and acceptance preserved before Checkout |
| Stripe test Checkout, signed webhook, retry, refund/dispute | Exactly one paid state and immutable receipt; adverse payment holds intake |
| Clean and EICAR fictional upload | Exact Blob version held Pending; Clean only promoted after matching scan, EICAR held Malicious; no cross-tenant access |
| Identity provider, email or app fails mid-flow | No charge without agreement; visible recovery and alert; rollback keeps records |
| Wix and phone/desktop public entry | Approved automatic-purchase wording and full accessible buyer journey |

Microsoft primary references: [customer tenant overview](https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam), [customer deployment planning](https://learn.microsoft.com/en-us/entra/external-id/customers/concept-planning-your-solution), [pricing/MAU FAQ](https://learn.microsoft.com/en-us/entra/external-id/customers/faq-customers). These establish candidate capabilities, not Salus-specific configuration or cost.
