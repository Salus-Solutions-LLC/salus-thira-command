# SalCAPA v3.113 — Phase 1 light-airy interface refinement

## Outcome

SalCAPA now presents the approved Phase 1 member-facing interface refinement aligned with the public Salus visual system while preserving the existing governed operating model, tenant boundaries, evidence controls, human authority, and operational workflows.

## Visible refinement

- White and near-white working surfaces replace the dense saturated shell.
- Salus blue provides restrained hierarchy for headings, navigation, and context.
- Salus orange is reserved for links, primary actions, and directional affordances rather than generic status meaning.
- Dark-neutral body text, light dividers, generous whitespace, and reduced visual density improve scanability.
- The Common Operating Picture is framed as **See and understand**.
- Command Center is framed as **Coordinate and act**.
- High-visibility workflows use shorter purpose lines, clearer current context, one primary action, and progressive disclosure of secondary controls.
- Investigation language uses the approved plain-language field labels and keeps Protected Member linkage separate from access/disclosure controls.

## Build and release integrity

- Immutable v3.43 archive evidence is verified in an isolated reference location instead of being reconstructed over current runtime/UI source.
- Regression controls fail closed if historical archive verification mutates current interface files.
- The exact release candidate must pass the complete governed validation family before freeze or Azure promotion.

## Controls preserved

This release does not weaken role or tenant isolation, sensitivity and disclosure controls, provenance, audit history, evidence lifecycle, human review and authority, recovery, rollback, passwordless Azure identity, or final release assurance. Frozen v3.112 remains unchanged until this exact candidate passes controlled release validation. Azure promotion is separately governed and uses the exact validated immutable artifact.
