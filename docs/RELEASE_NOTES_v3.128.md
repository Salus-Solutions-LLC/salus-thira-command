# SalCAPA v3.128 release notes

## Protection Advisor embedded-flow repair

- Replaces the 28-question expanded assessment wall with a bounded one-question-at-a-time flow.
- Adds clear question progress, Previous Question, Next Question, and final-results controls.
- Preserves every existing answer state, consent control, server-side answer persistence, preliminary result, account, retained-result, and package-recommendation behavior.
- Prevents the Wix-hosted Protection Advisor from expanding to approximately 5,576 pixels and creating competing page and iframe scroll positions.
- Keeps Wix authoritative for the public header, navigation, footer, and chat experience.
- Adds focused automated acceptance for the bounded question flow.

## Security and governance

- No authentication, tenant, Microsoft Graph, Entra, database, retention, or authorization boundary changes.
- No permission expansion.
- v3.127 remains the rollback release.
