# SalCAPA fictional demonstration environments

Status: bounded cross-functional implementation for Issue #124
Fixture version: `issue-124-cross-functional-v2`

## Purpose

This fixture layer creates repeatable, clearly labeled records for the three
fictional Protected Member environments required by Issue #124. It now stages a
governed See–Decide–Coordinate–Act–Prove journey for each environment. It does
not claim that a human has qualified intelligence, made a decision, authorized
work, verified evidence, approved a report, or accepted Azure promotion.

The environments are:

- Aster Ridge International Airport — fictional demonstration
- Cedar Vale Energy Systems — fictional demonstration
- Northstar Applied Technologies — fictional demonstration

Each receives one Draft baseline assessment, the four SalOPS service pillars,
and eight bounded personas spanning Protected Member and Salus responsibilities.
The member read-only persona uses the explicit `Protected Member Viewer` role so
it cannot inherit cross-member audit access.

Each environment also receives one coherent fictional journey with:

- a collected, unvalidated SalINTEL indicator awaiting analyst qualification;
- a SalTHIRA threat, scenario, capability target, evidence-needed record,
  capability gap, and proposed improvement with deliberately bounded confidence;
- an open SalCAPA coordination thread and an awaiting-decision request;
- a requested SalOPS planning action that has not been authorized; and
- cross-cutting PROVE-visible evidence and trace gaps that make the missing human
  review, decision, authorization, validation, and release steps explicit.

The three scenarios cover airport continuity during a regional outage,
control-center and field coordination during grid disruption, and protected
production continuity during supplier and telecommunications interruption.

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
- Baseline assessments remain Draft; intelligence remains Collected and
  Unvalidated; improvements remain Proposed; decision requests remain Awaiting
  Decision; operations requests remain Requested; and evidence remains Pending.
  Fixtures do not imply human review, approval, release, legal authority,
  organizational policy, or operational decision.
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
migration compatibility are verified. The next increment will exercise the
journeys through role-specific interfaces, cross-tenant denial, reports,
recovery, and rollback before Azure promotion.
