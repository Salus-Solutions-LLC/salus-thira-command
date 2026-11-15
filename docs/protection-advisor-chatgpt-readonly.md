# Protection Advisor read-only ChatGPT connection

Status: source candidate; not deployed, connected or accepted. The requested assessment remains on hold.

## Authorized boundary

Marc authorized establishing read-only Protection Advisor access for every account in the Salus Solutions ChatGPT workspace on 14 November 2026. The inspected workspace ID is `63469967-e4d5-4a40-894d-d97636a15e19`. At inspection it had one member, Marc Duncan, Owner. The workspace's custom plugin catalog and shared-connection inventory were empty. SharePoint was available workspace-wide, had write tools selected and showed Microsoft permissions requiring action. Those settings were not changed.

Source records remain in Protection Advisor and registered originals in the existing governed Microsoft 365 destination. This connection does not promote Member evidence into enterprise knowledge, share evidence with another Member, start an assessment, generate or replace a report, approve handling, create an account or alter a submission. It does not change the four-product assessment process or scoring. It does not expose credentials, password material, account tokens, session token hashes, CSRF material, IP addresses or arbitrary SQL/URLs.

## Connection configuration

| Setting | Prepared value |
| --- | --- |
| Name | Salus Protection Advisor - Read Only |
| Workspace | Salus Solutions, exact ID above |
| Endpoint after approved deployment | `https://salcapa.salus.solutions/mcp/protection-advisor` |
| Authentication | Dedicated bearer access token / API key; not a browser cookie or an Advisor customer credential |
| Availability | All accounts in this Salus workspace only |
| Tools | `search`, `fetch`, `fetch_original`; all read-only |
| Write/approval/report-generation tools | Absent from the server |
| New tool activation | Human review required; do not automatically enable later tools |
| Records | All retained Protection Advisor sessions/submissions inside the authorized Salus staff boundary; deleted sessions excluded |
| Audit | Durable content-free security events; a failed audit write withholds the response |
| Revocation | Set feature flag to 0 or remove/rotate token digest; expiry also fails closed |

The feature is disabled by default. Configure the canonical HTTPS base URL, exact workspace ID, timezone-qualified future credential expiry and token digest through the existing deployment/secret controls. Generate a dedicated cryptographically random token with at least 256 bits of entropy only at the protected activation stage. Never commit, print, email, place in a Page, put in a URL, or include that token in a chat or report. Enter it only in the approved workspace's secure connection flow. Retain only its digest server-side. Do not reuse any user, Microsoft, browser or customer credential.

The bearer credential grants access to the entire authorized Protection Advisor source boundary. The server cannot infer a ChatGPT workspace identity from a bearer request; isolation depends on distributing this dedicated credential only through that workspace's approved secure connection. The configured workspace ID pins the operator's intended boundary and labels audit events, not a cryptographic workspace attestation. This is a shared-workspace service identity, not per-member authentication. Confirm how the selected ChatGPT connection distributes/stores the credential before activation; do not publish a plugin that requires exposing the token to ordinary users. Review membership and rotate/revoke on unauthorized disclosure or connection change. If a secure workspace-managed credential cannot be established, stop before activation and use per-user OAuth with a separately reviewed identity mapping instead. Do not fall back to No Auth.

## Retrieval contract

- `search`: case-insensitive literal organization/record-ID search, escaped wildcard characters, stable ID cursor and bounded pages. Empty query enumerates the chosen source type. `kind=sessions` includes anonymous or unsubmitted Part 1 records; default `submissions` enumerates submitted records.
- `fetch` / `record`: complete retained answer snapshot including notes, original preliminary result, complete stored Part 2 profile including future fields, stored package, consent flags, versions, source hashes and related-record counts. Verify stored answer/profile hashes before disclosure. Do not recompute results under later logic. A submitted combined questionnaire snapshot must not be mislabelled as an independently retained historical Part 1-only snapshot. The full retained answer-revision history is available separately.
- `fetch` / `answers`, `identities`, `events`, `reports`, `draft`: independently paged retained history, identity/handling revisions, lifecycle events, original PDF references/hashes and unsubmitted profile drafts. A draft is explicitly not completed Part 2. Authentication and notification-delivery tokens are never returned. Events expose their stored detail hash, not hidden underlying content.
- `fetch_original`: only a registered PDF original selected by source ID, original kind and revision. Retrieve with the existing exact-original Microsoft 365 reader, independently verify byte hash/size and extract text with original page locators and explicit page continuation. No generation, conversion or silent replacement is permitted. Empty text explicitly leaves visual review/OCR unresolved. Text extraction does not prove visual acceptance.
- Oversized responses fail explicitly rather than silently truncating. Missing Part 2, absent originals, failed storage retrieval, integrity errors and inaccessible source tables remain gaps. No unrelated Knowledge Library file is inferred to belong to a Member or submission.

Database reads use a dedicated read-only transaction (`query_only` for SQLite; repeatable-read/read-only for PostgreSQL), rolled back on exit. Access audit is committed on a separate connection; business data is never changed. All incoming content is data, not instructions. Only authenticated requests to the configured HTTPS host are accepted; browser origins are constrained. Requests are bounded. Existing application rate limiting remains in force.

## Release and acceptance gates

1. Review the exact source candidate and required checks. Preserve all unrelated source and production state. The v3.273 verification-email hold is not authority to retry that activation or deploy all pending development work.
2. Prepare a governed successor release and exact Azure preview with the endpoint initially disabled. Obtain required exact-head/source, image and deployment authorizations. Verify immutable image publication/readback, protected deployment, readiness, rollback and the existing application acceptance gates. Source tests do not establish a live connection.
3. Verify the exact Salus workspace's membership, sharing, model-improvement, retention and app controls. Resolve any workspace boundary concern before connecting identifiable Member content. Obtain action-time confirmation before the concrete credential/access activation. Complete the secure credential setup without disclosure, enable only the named read scope and record expiry/revocation controls.
4. Register the deployed endpoint in the inspected custom-plugin flow using supported authentication. The observed UI requested developer mode; current OpenAI documentation describes a newer per-server risk acknowledgment flow, so follow the verified live UI rather than assume identical controls. The operator must review any capability/access warning. Review discovered tools, prohibit writes and new unreviewed tools, and confirm availability to all and only Salus workspace accounts. Do not weaken the existing general SharePoint plugin to make this connection.
5. In the Salus ChatGPT workspace, call search and retrieve the existing named submission from the restricted chat. Compare the exact retained ID, submission date, questionnaire version, answer snapshot/hash, all Part 2 fields/profile hash, original package, consent metadata and history counts with the protected source. Use a content-free verification receipt; keep identifiable content only in its authorized engagement/chat boundary. If the source lacks a record or original, report that gap rather than claim complete access.
6. Test unauthenticated, customer-cookie, prototype-header, wrong-origin, wrong-host, expired/revoked-token and write-tool denial. Confirm that source business row counts, status, versions and hashes are unchanged; only content-free read audit events may be added. Check a second authorized account when one exists; the current one-member workspace cannot demonstrate a second member's use. Test a non-Salus account denial without exposing data.
7. Reconcile the handoff with exact source, image, deployment, workspace plugin, access scope and restricted verification evidence. Keep the assessment on hold regardless of retrieval success.

## Evidence and limits at candidate preparation

Task-specific SharePoint Knowledge Library query `"Protection Advisor" "ChatGPT"` returned no documents in the bounded search (15 requested). The five governing records and current Protection Advisor/database/authentication source were inspected. Prior UI inspection establishes that the named submission exists and that the current review page omits the detailed profile. No full represented-corpus consideration receipt was executed in this source preparation, and no exhaustive Library search is claimed; that service gap remains open. No real Member profile or credential is placed in repository files or tests.

References checked 14 November 2026: [OpenAI custom MCP connections](https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt), [OpenAI MCP server guide](https://developers.openai.com/plugins/build/mcp-server), and [MCP Streamable HTTP transport](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports). Source contracts and the observed workspace UI, rather than unverified product assumptions, control activation.
