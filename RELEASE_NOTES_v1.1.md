# Salus THIRA Command v1.1 Release Notes

## Governed residual risk

v1.1 separates Current, Predicted Residual, and Validated Residual risk. Approved improvements may influence only the predicted forecast. Validated risk reduction requires completed implementation plus a controlled validation backed by currently Verified evidence.

Validation supports Validated, Partially Validated, and Failed outcomes. Failed validation earns no reduction and creates a corrective-action reassessment trigger. Direct edits to validation status are blocked.

Validated credit is dynamically revoked if supporting evidence is no longer Verified. Risk forecasting also follows the latest executive decision for an improvement, so historical approvals do not linger after a later Defer/Reject decision.

Each risk result carries a methodology version for historical transparency.

## Retained controls

v1.1 retains v1.0 direction-aware capability measures, v0.9 Accepted Risk governance, PostgreSQL/SQLite runtimes, tenant authorization, evidence governance, backup/DR, OIDC/session controls, security telemetry, and release security gates.
