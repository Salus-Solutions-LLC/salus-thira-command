# Salus THIRA Command Site Integration Contract — v1.15

## Purpose

This contract governs the Operational Risk and Professional Judgment Workspace in the approved Salus product Site. GitHub remains authoritative for product semantics. The Site may present an action as operational only when it calls the governed backend action and displays the persisted response.

## Risk workspace

- Read authoritative risk state through `GET /api/risk/{assessment_id}`.
- Display inherent, calculated current, professional assigned, predicted residual, and validated residual risk as separate columns.
- Never substitute professional assigned risk for calculated risk or use it in predicted/validated residual mathematics.
- When `professional_override_applicable` is false, do not display an assigned score as Current.
- Display `professional_override_unavailable_reason` and preserve access to `professional_override_record` for governed supersession or withdrawal.

## Governed professional actions

- Create a judgment through `POST /api/risk-overrides` with assessment, threat, assigned score, authority, reason, future review date, and optional eligible evidence.
- Review through `POST /api/risk-overrides/{id}/review`; cited evidence must still be Verified and lifecycle Current.
- Withdraw through `POST /api/risk-overrides/{id}/withdraw` with a documented reason.
- Do not expose ordinary edit or delete controls for professional-judgment records.
- Offer only Verified, lifecycle-Current evidence from the active assessment as supporting evidence.

## Persistence and safety

- Refresh risk and evidence lifecycle state from the backend before rendering.
- Show persisted responses and surface server validation failures.
- Preserve the approved simplified interface and withhold controls that are not connected to authoritative persisted actions.
- Do not display build numbers, branches, CI state, release gates, or engineering diagnostics in the primary product interface.
