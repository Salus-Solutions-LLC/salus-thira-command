# SalCAPA v3.138 Release Notes

## Mobile workspace usability

- Replaces the full stacked desktop sidebar on phone screens with an accessible off-canvas navigation menu.
- Keeps the active workspace immediately visible on mobile devices.
- Supports Menu-button, backdrop, navigation-selection, and Escape-key dismissal.
- Maintains correct `aria-expanded` and `aria-hidden` navigation state.
- Provides 44-pixel minimum touch targets and 16-pixel form controls to reduce accidental activation and mobile browser zoom.
- Adds phone-safe spacing, viewport safe-area support, full-width action controls, and bounded horizontal scrolling for data-heavy tables and route views.
- Uses reduced-motion preferences and preserves print behavior.

## Governance and compatibility

- Microsoft 365 intake remains bound to the approved **SalCAPA Intake** folder.
- OneDrive/SharePoint access remains exact-folder, read-only, tenant-scoped, and governed by existing role, sensitivity, and Protected Member boundaries.
- Human review remains mandatory before indexing, findings, SalTHIRA routing, decisions, or disclosure.
- No authorization, evidence, tenant-isolation, retention, or rollback control is weakened.
- SalCAPA v3.137 remains the accepted rollback release.

## Validation

- Regression tests verify mobile assets load after existing presentation assets.
- Tests verify responsive breakpoints, navigation accessibility, Escape dismissal, touch sizing, safe-area handling, reduced motion, and overflow controls.
- Candidate validation requires CI across SQLite, PostgreSQL, and production containers, CodeQL, contextual intake, and all path-applicable governed workflows.
