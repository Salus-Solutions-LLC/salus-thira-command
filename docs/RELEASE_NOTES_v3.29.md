# SalCAPA v3.29 release notes

## User-assigned managed identity selection

SalCAPA v3.29 supplies the Container App runtime identity client ID through the
Azure SDK's governed `AZURE_CLIENT_ID` selector. This lets the existing
`DefaultAzureCredential` consumers select the attached user-assigned identity
for PostgreSQL, Key Vault, and evidence storage without a client secret or
database password.

Deployment verification now compares the runtime selector with the actual
managed identity client ID. Passwordless-runtime regression checks and Azure
policy validation enforce the same contract. Readiness remains fail-closed if
the selected identity cannot acquire a token.

The bounded diagnostic redaction replacement is also corrected so captured
messages retain their field labels while sensitive values remain redacted.
