# Salus Discovery Conversations — candidate implementation and release record

**Date:** 3 October 2026. **Status:** Development source candidate; production disabled. **Authority:** Marc's Discovery Conversations build direction and approved naming architecture, recorded as SAL-D099 in this candidate. The Charter, Decision Register and exact approved artifacts continue to govern. This record is not approval of an exact software release, public enrollment or a retention schedule.

## What decision does this module support?

“What can we discover today that helps a Protected Member make a better decision tomorrow?”

Salus Insights publishes Salus research and analysis. Discovery Conversations lets people contribute experience, questions, disagreement, observations and perspective. Staff can preserve a useful contribution as a research candidate. A separate qualified process must validate evidence before the Salus Knowledge Library adopts it. The Salus Knowledge Flywheel connects discovery, knowledge, decisions, action, evidence, learning and further discovery. The Protected Members → SalCAPA™ → SalINTEL™ → SalTHIRA™ → SalOPS™ architecture and all six SalTHIRA steps remain unchanged.

The invitation is **“Don't just read our perspective. Add yours.”** The principal action is **Add Your Perspective**. Prompts invite missing perspectives, different interpretations, experience, comparable events, better questions and new research. There are no likes, votes, followers, popularity rankings, promotional notifications or engagement scores.

## Implementation boundary

`salus_discovery_conversations.py` registers with the existing FastAPI application after its shared helpers. `static/discovery-conversations.html`, `.css` and `.js` provide the public conversation and authenticated participation/review screens. No new application dependency, paid service, outbound notification, production setting, existing report method or commercial switch is introduced.

The application registers the module without creating its tables when `SALUS_DISCOVERY_ENABLED` is unset or `0`. Its page and API return a plain-language 503 hold. For an approved environment, set the flag at process startup; schema initialization uses the current database connection factory. Restart to apply configuration changes. Do not enable a flag in a running process that started without its schema.

The public route is `/discovery-conversations`. It uses the existing same-origin Salus session; production participation additionally requires the host's OIDC authentication mode. Prototype role/user/tenant headers cannot provide participation or moderator identity. This candidate supports approved existing accounts. It does **not** establish public account registration, email verification, a new identity provider or broader access to Member workspaces. Those remain separate identity-design and release gates.

## Connect an Insight and contribute

An assigned reviewer registers a previously published Insight through the staff form or `POST /api/discovery/insights`. Record its stable source ID, exact title, HTTPS URL, version/date and publication-review reference. The URL must be on `salus.solutions` or `www.salus.solutions`, under `/insights/` or `/post/`, without credentials, query or fragment. It is a reference only; the module does not fetch external content. Duplicate IDs resolve to the same conversation; changed source versions return a conflict for governed impact review.

After registration, use the conversation ID in a reviewed article link:

`https://salcapa.salus.solutions/discovery-conversations#conversation=CONVERSATION_ID`

The link label is **Discovery Conversations — Add Your Perspective**. Add it to each actual Insights article only after its site layout, article identity, deployment and publishing review. The current website route and CMS integration could not be independently verified: the public `/insights` request returned 403, and bounded repository/branch/SharePoint searches found no existing module artifact. No Wix page was changed or published. This is an implemented registry/link integration contract, not proof that the live Insights site is connected.

A signed-in participant chooses a public professional name and expressly accepts policy `discovery-2026-10-03-v1`. Account email, private display name, user ID, tenant ID, submission token, moderator reason and flagger identity are excluded from public responses. Public participation is intentional and separate from Protected Member records; do not import a Member assessment, file, protected observation or private result into this community. No file upload is accepted. Any future attachment feature requires SAL-D091 exact-object quarantine and screening before use.

Participants may submit a perspective to a published Insight, reply to a published contribution or ask a standalone Discovery Question. Questions and their titles are absent from public lists until the root contribution is approved. Reply branches stop after two reply levels. Each submission uses an idempotency reference; a retry returns its existing record, while a changed payload under that reference is rejected. Exact repeated perspective text in one conversation is rejected.

## Review, correction and abuse controls

Every new contribution is Pending. Staff approval publishes the exact reviewed version. An author edit removes the public version and returns the new version to review. Version checks reject stale edits and review decisions; concurrent reviewers cannot both approve the same version. An author withdrawal removes public access and cannot be overridden by an approval. Hidden, pending or withdrawn ancestors also suppress their reply branch. Restricted original text, hashes, revisions, consent and review events remain available through the staff history view.

The candidate retains review history without automatic deletion. It does not claim that the Advisor's retention rule automatically applies to public dialogue. Before release, Marc must determine the community's records/privacy wording, retention/legal-hold handling, name-change process and authorized erasure process. Withdrawal is removal from public view, not erasure. Existing Member exports and tenant backups do not include these shared community tables; a separate complete community backup/restore rehearsal, including its user-identity references, is required before activation. Do not enable community participation alongside a tenant restore that can replace participant user IDs without reconciliation.

Moderator authority requires all three: a server-authenticated active account; `System Administrator` or `Assessment Director` role; and explicit membership in both `SALUS_DISCOVERY_STAFF_TENANT_ID` and `SALUS_DISCOVERY_REVIEWER_IDS`. There is no default moderator tenant or reviewer. A Member administrator cannot moderate by role alone. Reviewers cannot approve their own contributions. Approval includes an exact-version privacy/rights check and recorded reason. Respectful disagreement is not a rejection reason.

Signed-in users can report concerns. One private flag record per reporter/contribution prevents repeated flag creation; reports never change ranking or automatically remove text. Staff records disposition and separately hides/rejects the contribution when warranted. Staff can close/reopen a conversation and pause/restore participation with a reason. A paused contributor can still withdraw existing contributions. Urgent privacy/security reports require staff attention; this channel is not an emergency service. The Salus contact route supports moderation review, name-change and privacy requests pending confirmation of its operational owner and response standard.

Writes require the exact request origin, the custom same-site form header and JSON content type. The request stream is capped at 32 KiB before parsing; typed fields reject unknown attributes, excessive text and invalid references. A honeypot, at most three source links, controlled-account participation and the host's existing request-rate protection supplement a database-backed limit of 10 participation writes per 10 minutes and 50 per UTC day. Shared database upserts serialize each actor's quota across processes. Only a short-lived quota counter is retained; this module stores no new IP/network identifiers. Staff moderation is separately governed and is not throttled by contribution quotas.

All contributed text is rendered through DOM text nodes, not HTML. The page uses a same-origin content-security policy, denies framing and disables caching of conversation/API responses. No automatic source-link fetch, third-party script or file/media preview is provided.

## Research candidates and learning

An assigned reviewer can capture the current published contribution as Question, Perspective or Research lead. Preserve its contribution ID, exact version/hash, summary, applicability, restrictions, reviewer and date. The candidate remains **Candidate — unvalidated**; there is no endpoint to declare it validated knowledge, publish a finding, change methodology, authorize operations or accept risk. Source edits, withdrawals and parent holds require candidate re-review. Candidate reads also recheck current source and ancestry, including concurrent changes.

For Knowledge Library transfer, separately record supporting and contrary originals, jurisdiction/time applicability, confidence, rights, privacy, qualified reviewer, disposition, supersession and refresh trigger under SAL-D025/SAL-D037/SAL-D060/SAL-D062. The new candidate queue is a bridge for future integration, not a deployed Library promotion service. No active or issued Member report changes; a later validated lesson requires its own SAL-D027 impact assessment.

## Validation and acceptance gates

| Check | Current proof | Remaining gate |
|---|---|---|
| Source recovery | Five governance files refreshed at base `47f6fad44a7b6cf81e208d86495ce4f7983aa197`; relevant approved repository standards and seven-slide presentation read | Exact final candidate review |
| Existing deployment | Handoff records accepted Advisor v3.210 | Live health endpoint was inaccessible in this turn; Discovery Conversations has no deployed release |
| Lifecycle/security | 16 real-host, session-backed SQLite tests pass; includes private identity projection, staff segregation, stale/concurrent review, edit hold, withdrawal, reply ancestry/depth, idempotency, flags, abuse pause, origin/body/schema/rate controls, default-off schema and bounded pagination | Exact-head Windows/Linux/PostgreSQL CI and security checks |
| Browser behavior | Edge headless, 1280×900 and 390×844: public reading, participant identity, submissions, standalone question, edit hold, staff publication, plain-text injection and keyboard focus passed | Live OIDC return journey, pagination/recovery and failure-path review |
| Accessibility | axe WCAG 2 A/AA, WCAG 2.1 AA and best-practice checks: zero violations and zero incomplete items for anonymous, participant and staff at 1280 and 390 pixels; no horizontal overflow; screenshots inspected | Screen-reader/manual full-flow review, 200%/400% zoom, nonexpert readback and exact deployed-version acceptance |
| Static security | Python compilation, JavaScript syntax and Bandit 1.9.4 pass locally | Exact-head CodeQL/dependency/repository checks where required |
| Recovery/operations | UUID records, restricted version hashes/events and default-off rollback boundary implemented | Community backup/restore, moderator response ownership, retention policy and production load/recovery tests |
| Program continuity | Source candidate, decision/naming record, artifact boundary and handoff prepared | SAL-D079 persistent uninterrupted processing remains unmet; no new scheduler or worker is claimed |

Run `python tools/ci_discovery_conversations_smoke.py` in a dedicated local test environment. It uses fictional tenants/accounts and a temporary SQLite database. CI also runs the same lifecycle on a disposable PostgreSQL 16 database, Linux and Windows. The PostgreSQL test switch is for the isolated CI database only.

## Authority and research boundary

The inspected authorities are the Charter, Decision Register, Handoff, Approved Artifacts and Startup Protocol; Knowledge and Records Architecture; Portfolio Coherence and Handoff Standard; Enterprise Decision-to-Proof Operating Standard; Thought Leader Research Standard; Three-Level Service Framework; and approved Salus System and Methodolgy presentation. The registered Project Instructions file is absent from development; the read-only Master project `AGENTS.md` supplies its existing startup, continuity, architecture, release and OPM requirements. No synced reference was changed.

Fresh review on 3 October 2026 read [OPM Plain Language](https://www.opm.gov/information-management/plain-language/) and [W3C form notifications](https://www.w3.org/WAI/tutorials/forms/notifications/). OPM supports clear headings, short focused paragraphs, whitespace and consistent limited fonts; it does not specify a universal Arial/Times New Roman pair. That document-font pair comes from Salus SAL-D040. The interface uses readable Arial and its print style uses Arial headings and Times New Roman body.

Search excerpts from [Elinor Ostrom's directly attributable Nobel interview](https://www.nobelprize.org/prizes/economic-sciences/2009/ostrom/164465-ostrom-williamson-interview-transcript/) raised a governance lead about participant involvement and monitoring. Retrieval of the full interview failed, and the Nobel lecture PDF returned 403. This remains an unfinished thought-leader-original review, not adopted doctrine or proof of an empirically validated transfer from common-resource governance to online dialogue. The opposing design consideration is that central pre-publication review may discourage participation or delay discussion; the candidate follows Marc's governance/privacy requirements, retains dissent and provides a review-request route. Measure review delay, reason quality and evidence usefulness during an approved pilot, without popularity rankings. The full thought-leader roster was not reverified. Public-source review, program knowledge-base review and these primary leads were bounded; no Protected Member upload was read or applied. Missing live-site, identity, research-original, recovery and operational proof remains explicit.

## Exact next action

Complete exact-head CI and inspect the source, participation/privacy wording and moderator/identity assignments. Then obtain the governed exact-version release determination, rehearse backup/restore, publish an immutable candidate and validate fictional OIDC/public/mobile/moderation journeys before enabling the module or publishing Insights links. Keep accepted v3.210 and all existing scanner/commercial controls unchanged until their separate authorized release paths qualify changes. If candidate activation fails, disable only the Discovery flag and restore the accepted application image; preserve community records and audit history for controlled recovery.
