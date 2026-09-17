# SalCAPA v3.126

## Purpose

Restore reliable Microsoft Entra single sign-on at the permanent SalCAPA address.

## Changes

- Uses `https://salcapa.salus.solutions/api/auth/oidc/callback` for the governed development runtime.
- Keeps the Azure-native callback path available in Microsoft Entra as a rollback route.
- Renders “Sign in with SSO” as a direct navigation link instead of relying on a JavaScript click handler.
- Adds regression checks for the callback and login link.
- Adds a Wix-embeddable Protection Advisor surface so Wix remains the single live source for the header, menu, and footer; future Wix shell changes require no SalCAPA navigation release.
- Refreshes the standalone fallback menu to the current Wix top-level navigation.
- Carries forward the governed Microsoft 365 intake correction validated for v3.125.

## Security and authority

- No Microsoft Graph or Microsoft Entra permission expansion.
- No client secret introduced; runtime remains managed-identity based.
- Deployment remains gated by the existing immutable image and protected-environment workflow.
