# SalCAPA platform architecture

SalCAPA is Salus Solutions' protective capability assessment and action methodology implemented through a secure, tenant-isolated operating environment for Protected Members and authorized Salus personnel. It turns intelligence, risk findings, responsibilities, decisions, and operational results into coordinated, accountable protective action.

SalCAPA is not software for its own sake. The Common Operating Picture, dashboards, reports, and workspaces are views and tools within the operating environment; they are not the definition of the product. SalCAPA is where a Protected Member's continuing protective program lives.

**Core promise:** We help Protected Members build and operate the capability to see risk early, decide with confidence, act in time, and prove that protective work was done.

## Commercial and operating lifecycle

SalCAPA supports a three-stage relationship that moves a Protected Member from diagnosis to implementation to sustained Protective Readiness.

1. **Diagnostic engagement** — a paid SalTHIRA-based baseline review that defines protected missions, critical assets, threats, hazards, capability gaps, priorities, and a governed 90-day action plan.
2. **SalCAPA implementation** — configure the operating model, including intake categories, validation and escalation rules, workflows, responsible owners, reporting cadence, risk and capability registers, Common Operating Picture views, member communications, and documentation standards.
3. **Ongoing Protective Readiness membership** — recurring SalINTEL monitoring and analysis, periodic reassessment, SalCAPA coordination, executive briefings, exercise support, incident support, and SalOPS implementation assistance.

The architecture therefore treats continuity, reassessment, accountability, and proof of completed protective work as first-class product requirements rather than optional reporting features.

## Bounded components

- **SalINTEL** collects information and controls qualification through relevance, credibility, validation, analysis, operational-significance review, and recurring monitoring.
- **SalTHIRA** applies a Salus-specific risk-assessment methodology informed by recognized THIRA principles to identify threats and hazards, establish context and capability targets, assess capabilities, identify gaps, determine change impact, support decisions, establish priorities, and govern reassessment.
- **SalOPS** receives service requests and authorized SalTHIRA actions, then governs implementation planning, assignment, execution, completion evidence, testing or verification, results, and feedback.
- **SalCAPA shared services** provide identity, tenancy, authorization, intake, evidence, audit/version history, reporting, workflow, records handling, privacy controls, recurring review cadence, member communications, and recovery.

Salus does not claim ownership of the underlying public THIRA framework. SalTHIRA denotes Salus' specific assessment methodology and implementation, informed by recognized THIRA principles and extended through SalCAPA governance, evidence, prioritization, decision, action, and reassessment controls.

## Governing protective-action lifecycle

The canonical lifecycle is:

**Signal or observation -> qualification -> assessment -> capability priority -> executive decision -> responsible owner -> authorized action -> completion evidence -> testing or verification -> result -> reassessment.**

This lifecycle must remain traceable across components and time. Responsibility, due date, approval, accepted risk, completion evidence, testing/verification, operational result, and reassessment state are governed records. Generic updates cannot forge component provenance, qualification, lifecycle state, executive authority, tenant, completion, audit history, handoff state, calculated values, or release state.

## Governed handoffs

1. A SalINTEL record remains `Collected` until an authorized qualification action occurs.
2. Only a qualified, assessment-linked finding can create one SalTHIRA reassessment trigger.
3. A SalTHIRA improvement or risk-treatment recommendation requires the appropriate Protected Member executive decision before it can create one authorized SalOPS request.
4. The authorized request records a responsible owner, required action, target or due date when applicable, and status without allowing client input to forge server-controlled authority or completion state.
5. SalOPS records implementation activity, completion evidence, testing or verification where required, operational results, and lessons.
6. An assessment-linked operational result creates a SalTHIRA reassessment trigger so outcomes become governed evidence and the protective program remains current.

## Durable advantage requirements

Branding alone is not a durable advantage. SalCAPA must demonstrate disciplined, repeatable delivery through persisted artifacts and governed workflows, including:

- a distinctive Salus assessment taxonomy and scoring logic;
- clear intake, validation, escalation, qualification, decision, and reassessment workflows;
- executive-ready risk, capability, priority, and action reporting;
- evidence that recommendations and actions are assigned, tracked, completed, verified or tested, and reassessed;
- practical SalOPS implementation playbooks and operational handoffs;
- defined information-governance, privacy, retention, provenance, and records-handling standards;
- traceable, anonymizable examples that can demonstrate movement from signal to decision to completed and verified action without exposing Protected Member data.

## User experiences

- Protected Members receive a role-aware Common Operating Picture of decision-ready intelligence, assessments, capability priorities, executive decisions, responsible actions, reports, verification status, and results.
- Authorized Salus personnel receive professional SalINTEL, SalTHIRA, and SalOPS workspaces according to role.
- Both experiences use the same authoritative tenant data, governed records, and audit/version history.
- Product-facing language emphasizes protective readiness, decisions, accountability, evidence, action, verification, and outcomes rather than software mechanics.
- `Dashboard`, `portal`, and `app` may describe individual interfaces when technically useful, but must not be used as the primary definition or positioning of SalCAPA.

## Audience positioning

**General:** SalCAPA(TM) is Salus Solutions' protective capability assessment and action methodology—an integrated operating environment that turns intelligence, risk findings, responsibilities, and decisions into coordinated protective action.

**Government and homeland security:** SalCAPA(TM) connects intelligence to assessment, assessment to capability priorities, and priorities to accountable action across prevention, protection, mitigation, response, and recovery.

**Commercial Protected Members:** SalCAPA(TM) gives leadership one disciplined way to see risk, assign action, coordinate response, document decisions, and strengthen readiness across the organization.

These audience-specific descriptions may vary in emphasis, but they must resolve to the same governed operating model and authoritative records.
