# SalCAPA fictional demonstration environments

Status: accepted three-member operational baseline; governed full-lifecycle walkthrough validation pending  
Fixture version: `issue-124-role-preflight-v3`

## Purpose

This fixture layer creates repeatable, clearly labeled records for the three
fictional Protected Member environments required by Issue #124:

- Aster Ridge International Airport — fictional demonstration
- Cedar Vale Energy Systems — fictional demonstration
- Northstar Applied Technologies — fictional demonstration

Each environment receives one Draft baseline assessment, the four SalOPS
service pillars, eight bounded personas, and a coherent
See–Decide–Coordinate–Act–Prove journey. The baseline intentionally leaves
intelligence, evidence, decisions, operations, improvements, and reports at
states requiring authorized human action. Preparing a fixture never represents
human review, approval, release, legal authority, policy, or an operational
decision.

## Accepted Azure baseline

Exact frozen v3.111 is deployed in the Azure development demonstration. The
governed live acceptance completed on 11 September 2026 and verified all three
fictional environments, 24 non-routable identities, role and tenant boundaries,
representative SalINTEL, SalTHIRA, SalCAPA, SalOPS, and PROVE journeys,
PostgreSQL persistence, cross-tenant denial, and preservation of the accepted
application configuration.

The live acceptance used a bounded temporary consumption job and removed it
after the walkthrough. It did not replace the deployed image, change traffic or
DNS, or introduce real Protected Member, personnel, investigation, or
operational information.

## Fixture contents

Each environment receives:

- a collected, unvalidated SalINTEL indicator awaiting analyst qualification;
- a SalTHIRA threat, scenario, capability target, evidence-needed record,
  capability gap, and proposed improvement with deliberately bounded
  confidence;
- an open SalCAPA coordination thread and an awaiting-decision request;
- a requested SalOPS planning action that has not been authorized; and
- cross-cutting PROVE-visible evidence and trace gaps that make missing review,
  decision, authorization, validation, and release steps explicit.

The three scenarios cover airport continuity during a regional outage,
control-center and field coordination during grid disruption, and protected
production continuity during supplier and telecommunications interruption.

## Full-lifecycle acceptance walkthrough

`tools/ci_salcapa_demo_full_lifecycle_smoke.py` exercises the normal
role-aware application interfaces in an isolated, disposable database. For
each fictional environment it verifies:

1. the collected indicator is hidden from Protected Members until a
   specifically identified fictional Salus analyst qualifies it;
2. qualified intelligence is handed to SalTHIRA and creates a reassessment
   need;
3. a separately identified fictional Protected Member executive records the
   issued decision and authorizes the requested demonstration action;
4. a fictional Salus operations coordinator completes the action and records a
   result and lesson;
5. the lesson is retained as an open validation need, a reassessment review is
   scheduled, and the coordination thread is closed with a documented basis;
6. separate fictional responsibilities prepare, review, approve, and release
   the immutable executive report snapshot;
7. only the Released report is available in the Protected Member view and
   JSON, CSV, and printable HTML are derived from that released snapshot; and
8. read-only and cross-tenant attempts fail closed.

Every simulated actor and transition is labeled as a fictional acceptance test.
The walkthrough proves application behavior; it does not claim that any real
person reviewed, approved, released, or authorized the records. It does not run
against the maintained Azure demonstration unless a later, separately governed
activation explicitly authorizes that action.

## Safety and governance

- No fixture is created during ordinary application startup.
- Production use is rejected.
- Invocation requires Issue #124 authority and the exact fictional-data
  acknowledgement.
- Reseed requires a separate exact confirmation and deletes only tenants whose
  slug, fixture key, and fictional-environment classification all agree.
- Untracked tenants and their records are preserved.
- Fixture identities have no password, use deterministic UUID subjects, the
  non-routable `example.invalid` domain, and the `demo-fixture` provider.
  They do not represent accepted Microsoft Entra identities.
- Baseline fixture records do not forge server-controlled lifecycle,
  provenance, authority, tenant, audit, calculated, disclosure, or release
  state.
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

Repository-only full-lifecycle acceptance:

```text
python tools/ci_salcapa_demo_full_lifecycle_smoke.py
```

A future Azure walkthrough requires its own validated activation, successful
migration and rollback preflight, bounded cost, temporary-resource cleanup, and
positive confirmation that the accepted v3.111 demonstration remains
unchanged on failure.
