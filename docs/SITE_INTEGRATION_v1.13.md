# Salus THIRA Command Site Integration Contract — v1.13

## Purpose

This contract governs the future evidence-lifecycle workspace in the approved Salus product Site. GitHub remains authoritative for product semantics. No Site may represent evidence creation, expiry, lifecycle review, risk credit, or reassessment as operational unless it persists the governed record and its audit/version effects.

## Evidence contract

- Evidence belongs to one authenticated tenant and assessment.
- Optional capability and scenario relationships must remain within that assessment.
- Verification and lifecycle currency are separate fields.
- Submitted lifecycle, stale, review, tenant, audit, timestamp, and version fields fail closed.
- Dates use strict `YYYY-MM-DD` values.
- Sensitivity clearance is enforced for create and read operations.

## Lifecycle contract

- Expired evidence becomes Stale automatically.
- The first stale transition creates one open evidence-lifecycle reassessment trigger.
- Repeated reads and sweeps do not create duplicate open triggers.
- A controlled review requires a documented note and a non-expired new validity date.
- Review restores Current, preserves verification status, resolves the trigger, and writes audit/version history.
- Stale evidence earns no validated-risk credit and cannot support an override that requires current Verified evidence.

## Publication boundary

The duplicate Site must not receive further product changes. Publication to the approved original Salus dashboard remains withheld until its owning workspace is available through the connected Sites control plane. This does not block authoritative backend development and release validation in GitHub.
