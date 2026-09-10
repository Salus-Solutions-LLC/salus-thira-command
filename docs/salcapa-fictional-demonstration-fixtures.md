# SalCAPA fictional demonstration fixture foundation

Status: bounded implementation for Issue #124
Fixture version: `issue-124-foundation-v1`

## Purpose

This fixture layer creates a repeatable, clearly labeled starting point for the
three fictional Protected Member environments required by Issue #124. It is a
foundation for the demonstration journey, not a claim that the full end-to-end
scenario data or Azure promotion has been accepted.

The environments are:

- Aster Ridge International Airport — fictional demonstration
- Cedar Vale Energy Systems — fictional demonstration
- Northstar Applied Technologies — fictional demonstration

Each receives one Draft baseline assessment, the four SalOPS service pillars,
and eight bounded personas spanning Protected Member and Salus responsibilities.
The member read-only persona uses the explicit `Protected Member Viewer` role so
it cannot inherit cross-member audit access.

## Safety and governance

- No fixture is created during ordinary application startup.
- Production use is rejected.
- Invocation requires Issue #124 authority and the exact fictional-data
  acknowledgement.
- Reseed requires a separate exact confirmation and deletes only tenants whose
  slug, fixture key, and fictional-environment classification all agree.
- Untracked tenants and their records are preserved.
- Fixture identities have no password, use deterministic UUID subjects, the
  non-routable `example.invalid` domain, and the `demo-fixture` provider. They do
  not represent accepted Microsoft Entra identities.
- Baseline assessments remain Draft. Fixtures do not imply human review,
  approval, release, legal authority, organizational policy, or operational
  decision.
- A manifest digest and immutable run record establish which fixture definition
  was applied and when.

## Operator interface

Seed:

```text
python -m salcapa_demo_fixtures --operation seed --authority ISSUE-124 --acknowledgement "FICTIONAL DEMONSTRATION DATA ONLY"
```

Reseed:

```text
python -m salcapa_demo_fixtures --operation reseed --authority ISSUE-124 --acknowledgement "FICTIONAL DEMONSTRATION DATA ONLY" --confirmation "DELETE AND REBUILD FICTIONAL DEMONSTRATION ENVIRONMENTS"
```

The deployment workflow must run this interface only after backup/recovery and
migration compatibility are verified. The next increment will add substantial
fictional SalINTEL, SalTHIRA, SalCAPA, SalOPS, and PROVE records and the critical
journey assertions required before Azure promotion.
