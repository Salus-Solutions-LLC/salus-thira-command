# Persistent assessment worker for SAL-D078

**Status:** implementation design for issue #588; not deployed or accepted.  
**Scope:** one authorized Protected Member, assessment level and work package at a time across SalINTEL™, SalTHIRA™, SalOPS™ and SalCAPA™.  
**Owner:** Salus engineering and assessment lead. **Release authority:** Marc and the established qualified reviewers.

## Failure being corrected

A chat turn stops when the assistant yields. The existing hourly same-chat automation starts separate, intermittent runs and can be missed when its host is unavailable. Neither mechanism keeps the source and report queue processing between turns. The 28 September Tierra Linda record shows the consequence: the assistant answered a status question, ended the turn and did no further research before the next message. Do not call the current workflow uninterrupted.

## Required operating result

After an assessment package is accepted and its authorized scope, budget and source rights are recorded, a durable service works the next eligible item without another Member message. It keeps working while actionable items remain, resumes automatically after a restart, and records actual active, idle, failed and human-wait intervals. A worker may not publish a report, determine a professional license question, accept risk, buy a service, expand access, or copy Protected Member data across tenants without the applicable approval.

## Implementation on the existing SalCAPA foundation

1. Use the existing Azure PostgreSQL, workload managed identity, private evidence storage, telemetry and immutable image/release path. Add a separate assessment worker deployment rather than making the hourly chat or knowledge-scan schedule the primary engine. The current application has zero minimum replicas, so its web process cannot serve as an always-on worker.
2. Persist a tenant-scoped `assessment_work_package` and `assessment_work_item` table. Required item fields: opaque tenant and engagement IDs, level, stable source/claim/gap ID, stage, priority, task type, input evidence references and hashes, access/rights classification, dependency IDs, attempt count, next eligible time, lease owner/expiry, checkpoint, output/version references, reviewer gate, and terminal disposition. Store restricted content in the governed evidence store, not in logs, job labels, GitHub, or a cross-Member queue.
3. Use PostgreSQL row locking or an equivalent lease for one writer per Member package and artifact identity. Claim one eligible item, checkpoint before and after every source retrieval and report mutation, and write an idempotency key for every side effect. On restart, recover expired leases and compare the checkpoint and artifact hash before resuming. A retry must not create a duplicate report or repeat a Member-facing action.
4. Keep four connected lanes: source acquisition and exact-page/attachment review; claim, contradiction and qualified analysis; same-level four-report disposition; exact-version document QA. A finding moves to the next lane only after its source, inference, uncertainty and restriction fields are present. A report mutation is staged, rendered and checked before it can replace the existing working draft. Human review and release remain separate terminal gates.
5. Run the executor in a dedicated Container App with an approved nonzero minimum replica or an equivalent event-driven durable service that immediately starts the next queued item. The executor must make its own allowed source and approved AI calls; it cannot depend on an open Codex chat. Keep model access, file rights, rate limits, per-package expense ceilings and network egress explicit. Pause only the affected task when a gate is hit and continue independent authorized items.
6. Emit an append-only processing event for claim, start, checkpoint, source/result hash, retry, failure, idle reason, human gate, report version and stop. Monitor queue age, observed active/idle time, lease expiry, restart recovery, failure rate, spend and package progress. Alert an owner on a stalled eligible queue; the hourly chat follow-up may remain an independent watchdog but is never proof of active work.

## State and stop rules

Items use `queued → leased → working → checkpointed → review_required / complete`, with `retry_wait`, `blocked_access`, `blocked_rights`, `blocked_expertise` and `failed_escalated` as explicit non-complete states. A worker that loses its process must leave a recoverable lease and last checkpoint. A work package stops only when every in-scope item has an evidenced disposition, the four report versions reconcile, required QA passes, and the governed human release decision is recorded; a bounded Level 1 item may close with a named gate and owner while the package remains open. Operator pause and cost ceiling are visible exceptions, not silent completion.

## Tierra Linda acceptance demonstration

Use a restricted test package seeded from one real, authorized Tierra Linda source-to-report item with no personal fields in test logs. During execution, terminate the worker after source extraction and again during staged report generation. Verify automatic recovery without a new Marc message, a single source disposition, no duplicate report, four consistent finding references, recorded outage and resume timestamps, and a visible next item. Confirm that access/rights and human-release gates stop the relevant action without stopping other safe work. Render the exact four Word versions and run the established confidentiality, blank-second-page, Arial-heading, Times-New-Roman-body, page-X-of-Y, source/privacy, accessibility and qualified-review checks. Record run ID, commit/image digest, queue state, costs, logs and reviewer sign-off. Only then mark SAL-D078 implemented for this workflow.

## Delivery sequence and authority

- **Design and code:** add migrations, worker, bounded source/report adapters, telemetry, tests and a development-only deployment specification in a reviewable PR. Preserve the existing SalCAPA workflows.
- **Dry run:** run the interruption and idempotency test with synthetic evidence, then a restricted Tierra Linda item under approved source rights. No client-facing release.
- **Promotion:** use the governed immutable-image, exact-candidate validation, Azure verification and rollback process. A persistent replica, model/API usage or expanded source access must have an approved cost and permission envelope before activation.
- **Acceptance:** Marc and the qualified reviewer inspect observed run/idle evidence and the four-report reconciliation. Until that happens, report the capability as not implemented and continue authorized active-turn work plus the hourly fallback without claiming continuity during gaps.

## Current gap

The queue, executor, dedicated deployment and acceptance evidence above do not yet exist in the governed release. Issue #588 remains open. This document is a build contract, not a claim that the Tierra Linda assessment or its four reports are complete.
