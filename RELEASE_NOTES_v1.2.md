# Salus THIRA Command v1.2 Release Notes

## Relational integrity

v1.2 prevents cross-assessment relationships in the core THIRA record chain. Related records must exist in the same assessment on both create and update. Assessment ownership of governed child records is immutable after creation.

The enforced relationships are Scenario → Threat/Hazard, Capability → Scenario, Evidence → Capability/Scenario, Gap → Capability, Improvement → Gap, Executive Decision → Improvement, and reassessment trigger → affected governed record when an affected ID is supplied.

## Safer data-entry workflow

The active assessment is now implicit in child-record forms. Principal relationships use assessment-scoped selectors instead of manually entered numeric IDs. This reduces accidental linking errors without removing IDs from audit, traceability, or exports.

## Methodology continuity

Application version advances to 1.2.0. Risk methodology remains 1.1.0 because no risk-scoring formula changed. v1.1 governed residual-risk behavior and v1.0 direction-aware capability measurement remain intact.
