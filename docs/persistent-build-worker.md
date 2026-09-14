# SalCAPA persistent build-worker contract

Issue: #370

## Purpose
This contract defines the repository-side behavior required for a persistent SalCAPA engineering worker. GitHub remains authoritative. The worker is a continuation engine, not a substitute for release governance.

## Required loop
A worker invocation must continue through as many safe steps as its execution window permits:

1. Read `docs/build-continuity.md` and current GitHub branch, issue, pull-request, and workflow state.
2. Confirm the authoritative work branch and current priority.
3. Acquire the repository concurrency lease through the workflow concurrency group.
4. Identify the first/root failing condition or the next coherent product increment.
5. Perform a bounded implementation or repair.
6. Run the cheapest trustworthy validation that can falsify the change.
7. If validation fails, diagnose the new first/root cause and repair it in the same execution window where safe.
8. If validation passes, advance immediately to the next safe step rather than stopping after one commit or one check.
9. Before release or Azure promotion, run the full required candidate gates on the exact candidate artifact.
10. Promote only the exact artifact that passed the required gates.

## Stop conditions
The worker may yield only when one of these is true:

- execution/runtime limits require the worker to exit;
- an external process is still running and no safe parallel step exists;
- all currently authorized work is complete and the next step depends on an external result; or
- Marc personally must perform an action unavailable to the authorized worker.

Internal engineering defects, failed tests, CI failures, CodeQL findings, packaging errors, Azure-policy failures, transient service failures, stale continuity records, and ordinary implementation problems are not stop conditions.

## Safety and governance
The worker must preserve:

- frozen-release immutability;
- tenant and role boundaries;
- source, provenance, evidence, and audit controls;
- accountable human authority;
- rollback and recovery capability;
- least-privilege passwordless Azure/GitHub federation;
- approved Azure cost posture;
- no DNS or public-production cutover without Marc's approval;
- no long-lived credentials or client secrets;
- no build/CI engineering status in Protected Member UI.

## Repository state contract
The machine-readable file `ops/build-worker-state.json` records only non-sensitive continuation metadata. It must not contain credentials, secrets, protected-member information, evidence, personal data, or confidential operational content.

The state file fields are:

- `schema_version`
- `mode`
- `authoritative_branch`
- `active_issue`
- `next_priority`
- `last_verified_head`
- `worker_status`
- `last_transition`
- `notes`

`worker_status` is one of `ready`, `validating`, `waiting_external`, `needs_human`, or `complete`.

## Concurrency
Only one persistent continuation workflow may hold the `salcapa-persistent-build-worker` concurrency group at a time. New runs cancel stale pending/running supervisor runs before acquiring the lease.

## Heartbeat and stall detection
Every supervisor run emits a concise summary containing:

- current repository head;
- current worker state;
- active issue and next priority;
- whether the run found actionable work;
- whether a human action is actually required.

The existing hourly ChatGPT automation remains enabled as an independent watchdog/recovery layer. It is not the primary persistent execution engine.

## Current priority chain
1. Issue #368 — finish archive/current-runtime isolation and validation-entrypoint repair.
2. Issue #337 + Issue #360 Phase 1 — revalidate the aesthetic candidate.
3. Full required candidate gates.
4. Promote the exact tested artifact to the Azure development demonstration.
5. Continue the next coherent unified SalCAPA roadmap increment.
