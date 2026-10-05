# Level 1A customer identity: provider-verified implementation candidate

**Status:** Pre-code QA addendum to `docs/level1a-public-buyer-identity-qa.md` and issue #721. No buyer application, flow, credential, SalCAPA switch or payment is activated by this document. A qualified exact-version design determination remains required before implementation.

## Observed provider state, 5 October 2026

- Marc approved creation of the Microsoft Entra External tenant **Salus Member Access**. Entra displayed tenant ID `c4582c39-7d49-4419-b504-005c31e69549`, domain `salusmemberaccess.onmicrosoft.com`, license Microsoft Entra ID Free, and Marc's signed-in Global Administrator role after he completed Authenticator enrollment.
- The tenant's App registrations page showed no applications owned by this administrator. The External Identities user-flow inventory showed **No user flows found**. This is a narrow portal observation; an all-app inventory and exact billing readback remain to be completed.
- The creation form selected `Azure subscription 1` and `rg-salcapa-dev`; the portal reported creation success. The new tenant's **Linked subscriptions** blade responded that the feature is unavailable for this tenant configuration, so a post-creation billing link has not independently been read back. Confirm it in Azure Cost Management before a public flow is opened.
- Microsoft states that managed identities and workload identities are not currently available in External ID and recommends certificate credentials over client secrets for confidential applications. The current SalCAPA workforce OIDC uses managed-identity federation; do not copy that credential path or enable shared workforce auto-provisioning for customers.

## Proposed customer application boundary

1. Register one single-tenant confidential web application **Salus Level 1A Buyer Access** in the External tenant. Use only the HTTPS callback `https://salcapa.salus.solutions/api/auth/customer/callback` and an exact, separately named customer OIDC configuration. Do not reuse the workforce client ID, issuer, state cookie, provider label, or preauthorized user mapping. Verify the callback path is implemented and protected before entering it in the provider. App creation and any credential are separate action-time security decisions.
2. Use a Microsoft-hosted customer signup/sign-in user flow attached only to that application. Select an email-verifying method after security review of recovery, MFA and abuse controls. Do not enable SMS or premium fraud add-ons without an exact price and approval. A verified email proves mailbox control; legal purchasing authority still requires the buyer's affirmative attestation bound to the agreement and scope.
3. Use a certificate-backed confidential-client assertion with the private key in the existing restricted Azure Key Vault and only the application identity authorized to read it. Register only the public certificate in External ID. Record expiry, rotation, alert and rollback behavior. Microsoft recommends a CA-signed certificate for production; obtain an exact cost/security decision before choosing one. Do not put a client secret or private key in source, a browser, or a public app.
4. Pin the External tenant ID and discovered issuer, expected audience, redirect, state, nonce, signature and expiry. Map each verified `(issuer, subject)` exactly once to one new isolated application tenant and only that buyer's order authority. An email or organization match never joins another Protected Member. Do not accept tenant or role from a browser request. Keep existing workforce OIDC and Member mappings unchanged.
5. Bind agreement acceptance, order version/scope hash, tax determination, Stripe Checkout, signed webhook, payment and immutable receipt to the same tenant and buyer. Failed authentication, changed scope, duplicate callback/webhook or provider outage must not charge, release a file or create another tenant/order.

## Proof before activation

- Review the exact app-registration settings, credential method and user-flow settings. Confirm Azure subscription linkage and actual MAU/add-on exposure. Keep the existing $75 budget alert; it is an alert, not a spending cap.
- Test a previously unknown fictional buyer, a repeated callback, changed email, other-buyer access, existing fictional Member, cross-tenant access, agreement version change, abandoned Checkout and recovery. Verify one isolated identity and no privilege elevation or duplicate charge.
- Test one signed Stripe sandbox payment and webhook through the new identity, one exact rev10 Word issue and immutable receipt, then one small fictional Clean/EICAR upload with exact Blob version held Pending until a matching result. Verify real failure alert and recovery. Public controls remain closed until qualified live-output review and rollback proof.

## Primary provider references

- Microsoft External ID security operations: https://learn.microsoft.com/en-us/entra/architecture/deployment-external-operations
- External tenant app registration: https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app
- External tenant certificate authentication: https://learn.microsoft.com/en-us/entra/identity-platform/how-to-web-app-node-use-certificate
- Customer user flows: https://learn.microsoft.com/en-us/entra/external-id/customers/overview-customers-ciam

