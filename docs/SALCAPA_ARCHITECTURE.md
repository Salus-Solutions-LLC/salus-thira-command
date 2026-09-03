# SalCAPA platform architecture

SalCAPA is the secure, tenant-isolated platform and Common Operating Picture for Protected Members and authorized Salus personnel.

## Bounded components

- **SalINTEL** collects information and controls qualification through relevance, credibility, validation, and operational-significance review.
- **SalTHIRA** identifies threats and hazards, establishes context and capability targets, assesses capabilities, identifies gaps, determines change impact, supports decisions, and governs reassessment.
- **SalOPS** receives service requests and authorized SalTHIRA actions, then governs assignment, execution, results, and feedback.
- **SalCAPA shared services** provide identity, tenancy, authorization, intake, evidence, audit/version history, reporting, workflow, and recovery.

## Governed handoffs

1. A SalINTEL record remains `Collected` until an authorized qualification action occurs.
2. Only a qualified, assessment-linked finding can create one SalTHIRA reassessment trigger.
3. A SalTHIRA improvement requires an approving executive decision before it can create one SalOPS request.
4. An authorized SalOPS request can record an operational result.
5. An assessment-linked operational result creates a SalTHIRA reassessment trigger so outcomes can become governed evidence.

Generic updates cannot forge component provenance, qualification, authorization, completion, audit history, or handoff state.

## User experiences

- Protected Members receive decision-ready intelligence, assessments, recommendations, requests, reports, and action status through SalCAPA.
- Authorized Salus personnel receive professional SalINTEL, SalTHIRA, and SalOPS workspaces according to role.
- Both experiences use the same authoritative tenant data and controlled records.
