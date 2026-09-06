# SalCAPA v3.38 Release Notes

## Shared SalINTEL investigative-domain foundation

SalCAPA now persists an extensible SalINTEL domain registry covering the approved
enterprise catalog, including implementation-authorized Personnel Assessment and
Facility Assessment. Prevention, Protection, Mitigation, Response, and Recovery
are cross-domain investigative lenses rather than separate repositories.

The shared investigative record preserves tenant and engagement context without
making the originating engagement the owner of all resulting Salus intelligence.
Server-controlled fields cover lifecycle, sensitivity, internal visibility,
disclosure, qualification, requested/authorized/completed tier, bounded scope,
checklist version, effort limits, approved source categories and exclusions,
commercial treatment reference, deeper-tier recommendation, completion, residual
unknowns, actors, timestamps, version events, and audit history.

## Bounded depth and human authority

Tier 1 Initial/Baseline, Tier 2 Enhanced, and Tier 3 Deep-Dive/Comprehensive hooks
require explicit Salus authorization. A tier completes only at its authorized
scope after human qualification. Unresolved questions remain governed gaps or
higher-tier recommendations and never silently expand scope or customer cost.
Tiers represent investigative depth, not danger/readiness, and therefore do not
use the red-yellow-green condition continuum.

Analytic items preserve the distinction between fact, reported information,
inference, judgment, hypothesis, allegation, assumption, contradiction, gap, and
unknown. Source bytes remain in the generic material capability; SalINTEL records
use human-approved source links.

Salus-internal work remains hidden from Protected Members. Tenant disclosure
requires separate Salus approval after qualification and bounded completion.
Individual item release and linked-source disclosure are independently governed.
Cross-tenant access fails closed.

Investigations, analytic items, and version events participate in deterministic
tenant backup/restore and PostgreSQL identity handling. Acceptance covers SQLite,
PostgreSQL 16, both production-container database modes, dependency audit, Bandit,
repository hygiene, Azure policy/infrastructure validation, CodeQL, and exact
v3.38 reconstruction.
