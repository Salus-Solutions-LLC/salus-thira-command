# Salus Protection Advisor internal prototype design and acceptance contract

Status: Proposed internal-prototype contract  
Roadmap authority: Issues #290 and #235  
Product name: Salus Protection Advisor™  
Public call to action: Find Your Salus Package  
Internal module: Service Recommendation & Pricing  
Trademark note: the ™ designation remains provisional pending trademark and common-law clearance.

## 1. Purpose and release boundary

The Salus Protection Advisor helps a prospective client describe its operating context and receive a specific, explainable, preliminary Salus service-package recommendation and price range. It supports a qualified Salus review; it does not replace professional judgment or create a commercial commitment.

The first increment is an isolated internal prototype. It may run only in a local or separately controlled staging context. This contract does not authorize:

- a public route, public DNS, or a link from www.salus.solutions;
- deployment to or modification of the accepted v3.112 Azure demonstration;
- access to SalCAPA Protected Member tenants, records, identities, or credentials;
- automatic scope, price, discount, invoice, charge, contract, renewal, tier, membership, or onboarding decisions;
- paid external services, standing infrastructure, or additional Azure resources;
- use of real prospect, Protected Member, personnel, protectee, investigation, credential, or operational data in tests.

The Advisor receives a separate controlled release. Failure of any Advisor prototype, test, or release must leave the accepted SalCAPA demonstration and every frozen release unchanged.

## 2. Human and methodological authority

People lead. Salus methods guide. Technology supports. Evidence proves.

The Advisor may collect answers, apply a versioned policy, compare governed packages, prepare alternatives, estimate non-binding ranges, and explain the basis and limitations. A qualified Salus reviewer retains authority over the final scope, package, price, discount, investigation depth, commitment, and release.

The interface must use these distinctions consistently:

- SalINTEL develops qualified intelligence.
- SalTHIRA identifies risk and establishes priorities while authorized people decide.
- SalCAPA coordinates Protected Members, information, decisions, and action.
- SalOPS implements, sustains, and improves protective capability.
- PROVE supplies cross-cutting evidence, accountability, results, validation, traceability, learning, and improvement.

A prospect questionnaire is not a SalINTEL finding, SalTHIRA assessment, investigation, threat judgment, suitability judgment, contract, or Protected Member record. Prospect-reported information must remain labelled as reported information until a separately authorized Salus process qualifies or validates it.

## 3. Experience contract

### 3.1 Prototype entry

The internal prototype starts without a customer account. A test-only entry page identifies the experience as an internal demonstration using fictional data. It exposes no authenticated SalCAPA navigation, tenant selector, Protected Member name, or internal engineering metadata.

The later public entry label is Find Your Salus Package. The later navigation label is Service Advisor. Neither public label is activated by this increment.

### 3.2 Progressive journey

The prototype presents one understandable topic at a time and permits review before submission:

1. organization and mission;
2. industry and operating environment;
3. geography, jurisdictions, and locations;
4. personnel, populations, principals, assets, and critical operations;
5. dependencies and continuity needs;
6. existing prevention, protection, mitigation, response, and recovery capability;
7. reported threats, hazards, risks, vulnerabilities, and recent material changes;
8. urgency, desired support, and preferred investigation depth;
9. budget or affordability context, where the visitor elects to provide it;
10. contact, consent, and submission only when the visitor chooses to save or submit.

Questions adapt through explicit, versioned rules. Hidden questions cannot silently contribute values. Skipped, unknown, not applicable, and declined answers remain distinct.

### 3.3 Results

The results heading is Your Salus Recommendation. Results must show:

- the preliminary organization and operating profile;
- a primary package and, where useful, lower- and higher-scope alternatives;
- the reasons each package fits the reported needs;
- included services and explicit exclusions;
- Initial Pass, Intermediate Assessment, or High Deep-Dive as the recommended assessment depth;
- recommended implementation period;
- one-time and recurring price ranges, never a falsely precise price;
- optional services and the conditions that make them relevant;
- assumptions, contradictions, information gaps, and important unknowns;
- the governing questionnaire, recommendation-policy, package-catalogue, and public-price-policy versions;
- a clear statement that a qualified Salus reviewer must approve final scope and price;
- what happens next and how the visitor may stop, revise, save, or submit.

Red, orange, amber, and green may appear only for genuine condition or readiness measures. They must not encode investigation depth, workflow stage, approval, membership, or completion.

## 4. Assessment model

The prototype evaluates these independent dimensions:

- Exposure
- Threat and hazard environment
- Vulnerability
- Consequence
- Capability
- Complexity
- Urgency
- Service intensity

Capability is represented separately across prevention, protection, mitigation, response, and recovery.

### 4.1 Server-controlled evaluation

Evaluation occurs on the server against immutable policy snapshots. The browser may render questions and explanations but must not contain proprietary scoring weights, internal rates, margin floors, or binding package logic.

Each dimension result contains:

- a bounded band or descriptive state;
- supporting answer identifiers;
- assumptions and missing inputs;
- contradictions requiring clarification;
- uncertainty and confidence explanation;
- the policy version used;
- an explanation suitable for a prospective client;
- a separate Salus-only rationale where needed.

The model must not infer that organizational size alone establishes need, risk, maturity, affordability, or package level. It must support a small restaurant, local business, corporation, critical-infrastructure operator, public agency, county, state, and major multi-jurisdiction government without using a single size proxy.

### 4.2 Investigation depth

The public names are:

- Initial Pass
- Intermediate Assessment
- High Deep-Dive

These names map through a versioned internal policy to the existing governed commercial-engine investigation tiers. The mapping is not a danger, threat, readiness, approval, or membership scale. A recommendation remains preliminary and can be changed only through an identified Salus review with a recorded rationale.

## 5. Package and pricing contract

### 5.1 Governed inputs

The recommendation policy may use approved, versioned inputs for:

- product line and investigative domain;
- professional roles and labor estimates;
- number and type of locations;
- personnel and population exposure;
- geography and jurisdictional complexity;
- assessment or investigation depth;
- research, information, technology, and direct costs;
- travel, Global Partners, equipment, and specialist resources;
- planning, training, and exercise requirements;
- ongoing monitoring and support;
- contingency, minimum engagement, scope ceilings, capacity limits, and margin floors.

The prototype reuses the existing SalCAPA commercial engine through a narrow adapter. It must not duplicate or weaken the engine’s rate-card approval, source, estimate, correction, or human-authorization controls.

### 5.2 Separation of public and internal values

Public output may contain only an approved currency, rounded range, cadence, stated assumptions, inclusions, exclusions, and option labels. The adapter must never return:

- loaded labor cost or internal cost;
- hourly role rates;
- margin, contribution, markup, contingency formula, or minimum-margin rule;
- override order or proprietary weight;
- Global Partner rate or confidential supplier information;
- another prospect’s or Protected Member’s information;
- internal notes, source locations, tenant identifiers, or approval credentials.

Every price range records the exact internal estimate snapshot and sanitized public-output policy used. Changing a rate card, package catalogue, mapping, or rounding policy does not rewrite an existing result.

### 5.3 Package alternatives and authority

Where useful, alternatives may communicate a practical entry point, the recommended scope, and a stronger-capability path. Labels must describe scope and outcomes rather than imply that a smaller organization deserves less protection.

No calculation creates a charge, invoice, contract, scope expansion, tier change, renewal, customer obligation, or Global Partner action. The prototype provides no payment collection.

## 6. Information boundary and lifecycle

### 6.1 Isolation

Advisor data is outside Protected Member tenancy. It uses a distinct schema or datastore boundary, distinct service identity, distinct authorization policy, and distinct backup set. It cannot query, join, search, index, or derive from authenticated SalCAPA tenant data.

The prototype uses only fictional fixtures. It does not share sessions, cookies, tokens, cache keys, object identifiers, or file storage with authenticated SalCAPA.

### 6.2 Ephemeral session

Before explicit save or submit consent:

- the server issues an opaque, short-lived, rotation-capable session identifier;
- no contact information is required;
- the session contains only data necessary to complete the assessment;
- retention is short and versioned;
- expiry and deletion are enforced server-side;
- analytics, if later authorized, must not reconstruct questionnaire content or identity.

Browser state is display convenience only and cannot establish recommendation, consent, retention, review, or submission state.

### 6.3 Save or submit

Contact information is requested only when a visitor elects to save or submit. The interface explains purpose, recipient, intended retention, what happens next, and how to withdraw or correct information before affirmative consent.

Save or submit creates a controlled prospect record, not a Protected Member or SalCAPA account. Consent evidence records:

- notice version;
- purpose;
- fields authorized for retention or transmission;
- affirmative action;
- day-month-year date and 24-hour time;
- expiration or retention rule;
- correction, withdrawal, and deletion state.

### 6.4 Onboarding handoff

Only an authorized Salus user can accept a prospect for onboarding. The handoff creates a new, reviewable Protected Member onboarding draft from an explicit field-level transfer manifest. It does not grant access, activate membership, establish legal terms, copy internal Advisor notes, or silently reclassify reported information as verified.

The prospect record and transfer manifest remain linked for audit. Subsequent corrections and supersession preserve history.

## 7. Proposed immutable record contract

The prototype implementation should introduce a separate module and tables with an Advisor-specific prefix. The minimum record set is:

- advisor_questionnaire_versions — immutable released question and branching snapshots;
- advisor_recommendation_policy_versions — immutable dimension and package-selection rules;
- advisor_package_catalogue_versions — immutable package, service, inclusion, exclusion, and capacity definitions;
- advisor_public_price_policy_versions — immutable range, rounding, and disclosure policy;
- advisor_sessions — opaque session, expiry, lifecycle, and latest answer-revision references;
- advisor_answer_revisions — append-only answer changes with question-version lineage;
- advisor_evaluation_snapshots — dimension states, basis, gaps, contradictions, uncertainty, and policy hashes;
- advisor_recommendation_snapshots — package alternatives, reasons, assumptions, scope, and public price ranges;
- advisor_consents — immutable notice, purpose, scope, action, and lifecycle evidence;
- advisor_prospects — controlled retained prospect records created only after consent;
- advisor_review_decisions — identified Salus review, disposition, rationale, and supersession;
- advisor_onboarding_transfers — field-level authorized transfer manifests;
- advisor_audit_events — security, lifecycle, access, review, release, correction, deletion, and denial evidence.

Released policy versions and recommendation snapshots are immutable. Corrections create superseding records. Every snapshot includes a canonical content hash and the exact upstream version hashes.

## 8. Prototype service boundary

The initial internal prototype contract should expose only Advisor-specific endpoints under a disabled-by-default internal prefix. Suggested operations are:

- start an ephemeral fictional-data session;
- fetch the released questionnaire and permitted help text;
- validate and append an answer revision;
- evaluate the current session;
- retrieve the sanitized preliminary recommendation;
- record fictional consent and create a fictional prospect submission;
- list and review fictional submissions for explicitly authorized Salus roles;
- prepare, approve, or reject a fictional onboarding transfer without creating a tenant.

All state transitions are server controlled. Requests use strict schemas, field allowlists, request-size limits, bounded collection sizes, normalized enumerations, replay protection for state changes, and generic external errors. Unknown policy versions, expired sessions, mismatched snapshots, invalid transitions, disabled features, or unavailable dependencies fail closed.

The prototype must not attach these routes to the accepted public application configuration. Activation requires a separate feature flag, environment allowlist, and controlled release gate.

## 9. Security, privacy, and abuse controls

Before any limited public pilot, evidence must show:

- threat modelling for anonymous intake and pricing disclosure;
- rate limiting by privacy-preserving signals with bounded lockout behavior;
- CSRF protection for cookie-authenticated changes and strict origin checks;
- secure, HttpOnly, SameSite cookies where cookies are used;
- session rotation, expiration, replay denial, and fixation resistance;
- input normalization, output encoding, content-type enforcement, and injection tests;
- no unrestricted uploads or free-form executable content;
- no secrets, stack traces, database identities, formulas, or internal rates in responses or logs;
- least-privilege identity with no Protected Member data permissions;
- encryption in transit and at rest;
- data minimization, documented retention, correction, withdrawal, and deletion;
- restricted staff review roles and audit isolation;
- CSP, framing, referrer, cache, and transport-security headers;
- bot and denial-of-service protections with a usable human fallback;
- dependency, Bandit, CodeQL, repository-hygiene, and production-container gates;
- privacy and legal review of notices, consent, trademark presentation, and intended use.

Abuse controls must not claim that a visitor is a threat, fraudulent, or malicious. They may describe observed request behavior and the resulting temporary protection measure.

## 10. Accessibility, mobile, and visual doctrine

The prototype uses the Salus visual language already present in the repository and becomes the first governed consumer of the future shared Salus Digital Design System. A later design-system extraction must preserve approved logos, color, typography, controls, spacing, photography, graphics, and writing voice across www.salus.solutions, the Advisor, and authenticated SalCAPA.

Acceptance requires keyboard operation, visible focus, semantic headings, labelled inputs, understandable errors, accessible progress, screen-reader status updates, adequate contrast, reduced-motion support, zoom and reflow, and practical mobile and desktop layouts. Color alone cannot communicate meaning.

Dates are displayed day-month-year. Times use the 24-hour clock. The internal prototype does not display a SalCAPA release version because it is a separately released product; authenticated SalCAPA retains its left-margin release-version display.

## 11. Explainability and trust

Every question must explain, through progressive disclosure where useful:

- why Salus asks it;
- how the answer can affect the preliminary recommendation;
- whether it is required;
- how unknown, declined, or not-applicable answers are handled;
- whether the information is retained before submission;
- who can review it;
- what happens next.

Results distinguish reported information, assumption, information gap, contradiction, preliminary inference, and Salus-reviewed recommendation. They use Demonstrated, Partially Demonstrated, Evidence Needed, Improvement Underway, and Awaiting Validation only where the evidence state supports those terms.

The experience never says or implies that Salus personnel observed, reviewed, verified, approved, or decided something unless the corresponding governed human action exists.

## 12. Recovery, rollback, and graceful degradation

The prototype must have deterministic schema creation and reconstruction, versioned fictional seed data, backup and restore for Advisor records, and a tested deletion/expiry path.

Rollback disables the Advisor routes and restores the last accepted Advisor code and schema-compatible state without touching SalCAPA traffic, databases, identities, or releases. Forward-only data changes require an explicit compatibility and rollback plan.

If recommendation or pricing evaluation is unavailable, the interface preserves entered fictional-session data within its authorized lifetime, explains that a preliminary result is temporarily unavailable, and offers a human contact path only after consent. It must not invent a result, expose a partial internal calculation, or silently submit data.

## 13. Minimum-cost implementation sequence

1. Accept this design and test contract through a controlled validation pull request closed without merge.
2. Implement the separate Advisor models, immutable policies, fictional fixtures, and server-controlled evaluation adapter behind a disabled internal flag.
3. Add unit and integration tests for versioning, branching, uncertainty, price sanitization, lifecycle, denial, recovery, and rollback.
4. Add an internal fictional-data interface using existing repository-native patterns; do not deploy it publicly.
5. Conduct Salus review of questions, recommendation logic, package mappings, price ranges, language, and appearance.
6. Complete security, privacy, accessibility, mobile, and abuse acceptance.
7. Prepare a separate, reversible staging release.
8. Only after explicit approval, conduct a limited public pilot and later a separately governed public release.

No step authorizes paid infrastructure. A later staging or public deployment must pass its own Azure cost, identity, tenancy, recovery, rollback, privacy, and release gates.

## 14. Internal prototype acceptance matrix

The first implementation is accepted only when all of the following are evidenced:

- Representative fictional cases include a small restaurant, a multi-location commercial organization, a critical-infrastructure or public-service operator, and a major multi-jurisdiction entity.
- Size alone does not determine a dimension, investigation depth, package, or price.
- Each of the eight dimensions and five capability mission areas is independently traceable to explicit answers and a released policy version.
- Unknown, declined, not applicable, contradictory, and missing answers remain distinct and affect uncertainty transparently.
- Questionnaire branching is deterministic, versioned, server controlled, and cannot score hidden unanswered fields.
- Initial Pass, Intermediate Assessment, and High Deep-Dive map to governed commercial-engine inputs without representing danger or readiness.
- Package alternatives have explicit inclusions, exclusions, capacity ceilings, implementation periods, and applicable options.
- Public price output is a rounded range with cadence and assumptions; internal rates, costs, margins, overrides, formulas, and other-client information are absent.
- No recommendation or submission creates a binding or financial event.
- No pre-consent session requires contact information or creates a retained prospect.
- Consent, save, submit, correction, withdrawal, expiry, deletion, and review transitions are explicit and auditable.
- No public or prospect role can access a Protected Member route, tenant identifier, record, search result, backup, session, or credential.
- Onboarding transfer is field-level, authorized, reviewable, non-activating, and cannot silently promote reported information to verified fact.
- Exact policy, package, pricing, answer, evaluation, recommendation, consent, and review snapshots can be reconstructed deterministically.
- SQLite, PostgreSQL 16, production-container, dependency-audit, Bandit, repository-hygiene, Azure-policy/infrastructure, CodeQL, backup/restore, rollback, and established archived capability gates pass on the exact candidate.
- The accepted v3.112 demonstration, v3.111 rollback baseline, main, development/v1.17, release/v1.16, and every frozen release remain unchanged.

## 15. Deferred public-release requirements

The following remain required but are not authorized by this design increment:

- public DNS and www.salus.solutions integration;
- real prospect data and production retention;
- final privacy notice, terms, consent language, and trademark clearance;
- production rate-limit and abuse-service selection;
- production identity, secrets, observability, backup, budget, and incident response;
- external analytics, marketing, CRM, email, payment, or other connector;
- a limited public pilot;
- production release and post-release monitoring.

Deferral does not close or remove these requirements. Each needs explicit evidence and a separate controlled release decision.
