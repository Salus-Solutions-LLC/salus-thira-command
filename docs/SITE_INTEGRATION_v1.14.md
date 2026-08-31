# Salus THIRA Command Site Integration Contract — v1.14

## Purpose

This contract governs the Gap and Improvement Workspace in the approved Salus product Site. GitHub remains authoritative for product semantics. The Site may present an action as operational only when it calls the governed backend action and displays the persisted response.

## Gap workspace

- Create gaps through `POST /api/gaps`; new records always start Open.
- Limit capability choices to the active assessment.
- Display gap type, severity, description, root cause, owner, and persisted lifecycle state.
- Change state only through `POST /api/gaps/{id}/transition` with a documented reason.
- Do not place lifecycle state in a generic create or edit form.

## Improvement workspace

- Create improvements through `POST /api/improvements`; new records always start Proposed with Pending validation.
- Limit gap choices to the active assessment.
- Display the server-returned priority score and its authoritative factors; do not calculate or submit priority state in the Site.
- Change state only through `POST /api/improvements/{id}/transition` with a documented reason.
- Completion must display the resulting open Capability Validation reassessment trigger.
- Validate only through `POST /api/improvements/{id}/validate`, offering evidence that is both Verified and lifecycle Current.
- Display validation evidence, outcome, effectiveness, validator, timestamp, and resolved or corrective reassessment state from persisted records.

## Publication boundary

Do not publish this workspace to a duplicate Site. Publication to the approved original Salus dashboard remains withheld until its owning workspace is available through the connected Sites control plane. Incomplete controls must remain hidden rather than represented as operational.
