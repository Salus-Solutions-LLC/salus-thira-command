# Salus THIRA Command Site Integration Contract — v1.16

## Purpose

This contract governs the Executive Decisions and Accepted Risk Workspace in the approved Salus product Site. GitHub remains authoritative for product semantics. The Site may present an action as operational only when it calls the governed backend action and renders the persisted response.

## Executive decision workspace

- Read the active assessment's decisions through `GET /api/decisions?assessment_id={id}`.
- Create an append-only decision through `POST /api/decisions`.
- Offer only the enumerated decision types returned by the product contract.
- Require authority and rationale for every decision.
- For Accept Risk, require residual exposure, risk owner, reconsideration trigger, and future review date.
- Review a decision only through `POST /api/decisions/{id}/review`.
- Do not expose ordinary edit or delete controls for decision records.

## Accepted-risk workspace

- Read accepted risks through `GET /api/accepted_risks?assessment_id={id}`.
- Accepted risks are created only by a persisted Accept Risk decision; never show an independent create action.
- Permit descriptive updates through `PUT /api/accepted_risks/{id}` only for title, risk statement, residual exposure, owner, and reconsideration trigger.
- Review lifecycle currency through `POST /api/accepted-risks/{id}/review`.
- Change status only through `POST /api/accepted-risks/{id}/transition` with Under Review, Closed, or Superseded and a documented basis.
- Return an Under Review record to Active only through the controlled review action.
- Do not offer actions that reopen Closed or Superseded records.
- Display decision authority, current status, review lifecycle, review date, owner, residual exposure, and reconsideration trigger distinctly.

## Persistence and safety

- Refresh decision, accepted-risk, and reassessment-trigger state before rendering.
- Show persisted responses and surface server validation failures.
- Preserve the approved simplified interface and withhold controls that are not connected to authoritative persisted actions.
- Do not display build numbers, branches, CI state, release gates, or engineering diagnostics in the primary product interface.
