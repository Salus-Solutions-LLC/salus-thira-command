# SalCAPA v3.133

## Azure Monitor export for Protection Advisor load telemetry

- Preserves the privacy-preserving `protection_advisor_page_load` event introduced in v3.132.
- Propagates the structured event to the root OpenTelemetry handler configured by Azure Monitor while retaining the existing structured stdout record.
- Keeps the event schema limited to timestamp, event type, severity, load duration, navigation type, and embedded-page state.
- Adds no name, email address, organization, assessment answer, session token, IP address, or other direct identifier to the performance event.
- Preserves scale-to-zero behavior, the Wix embed contract, Part 1 and Part 2 behavior, identity, authorization, tenant, retention, and disclosure controls.
