# SalCAPA Build Continuity and Anti-Stoppage SOP

Status: governed candidate under Issue #298  
Applies to: SalCAPA build, validation, release, deployment, and maintained-development-demonstration work  
Objective: no silent stoppage and no avoidable multi-hour loss

## 1. Purpose

This procedure keeps critical SalCAPA work observable, recoverable, cost-conscious, and reconstructable from GitHub. It does not promise that interruption is impossible. GitHub, Azure, credentials, billing controls, runners, and the scheduling platform can fail. The operating requirement is to detect a stoppage promptly, classify it correctly, continue safe work, recover through the smallest bounded action, and positively verify that work resumed.

GitHub branches, commits, frozen releases, issues, pull requests, workflow results, deployment acceptance records, and continuity records remain authoritative. Conversation availability, title, duplication, or loss cannot block reconstruction.

## 2. Roles and authority

- **Primary build process:** performs the authorized bounded increment and records verified changes.
- **Independent continuity watch:** checks the primary process, GitHub execution, continuity state, and unresolved blockers without duplicating build work.
- **Salus release authority:** retains approval, release, disclosure, commercial, legal, policy, and operational authority.
- **Marc action:** requested only when recovery requires account-holder authority, billing changes, interactive identity work, or another action the connected tools cannot lawfully perform.

A process must never claim that a person reviewed, approved, decided, validated, released, or authorized work unless that person actually did so.

## 3. Heartbeat and staleness

For an hourly critical process:

1. Verify that the process is enabled.
2. Verify the most recent run actually began; an enabled setting alone is not execution evidence.
3. Verify that the run either completed, is still making bounded progress, or has a classified blocker.
4. Verify that the continuity record identifies the frozen release, active branch, active issue/increment, validation candidate, gate state, genuine blocker, and next authorized step.
5. Treat absence of a verified start for more than two expected hourly cycles as a continuity incident requiring immediate classification and recovery or escalation.
6. Never launch a duplicate build, validation, or deployment merely because a status is delayed or temporarily unavailable.

The independent watch should check at least hourly while critical build or deployment work remains active. It must remain separate from the primary process so the build is not solely responsible for detecting its own stoppage.

## 4. Required preflight

Before each increment:

1. Read GitHub state and compare it with both continuity records.
2. Search for existing issues, candidate branches, pull requests, workflow runs, acceptance evidence, and releases to prevent duplication.
3. Confirm the next action is within the approved roadmap and current cost discipline.
4. Confirm that frozen branches and releases will remain unchanged.
5. Confirm that required identity, tenancy, provenance, recovery, rollback, validation, and human-authority controls remain in force.
6. For any materially expensive action, verify financial readiness from an authoritative billing source when available.

Service availability and financial runway are separate facts. Financial reporting must use only:

- **VERIFIED SUFFICIENT**
- **OPERATIONAL BUT FINANCIAL RUNWAY NOT DIRECTLY VERIFIED**
- **ACTION REQUIRED**

Reachability, a recent successful job, or absence of an alert is not direct billing evidence.

## 5. Interruption classification

Classify the interruption before retrying:

| Class | Evidence | Bounded response |
|---|---|---|
| Application or test defect | A workflow step ran and produced a reproducible failure | Diagnose the failing contract, repair only the defect, and rerun the required exact-head gates. |
| Runner or workflow-start failure | Jobs fail or remain queued before executable steps begin | Check Actions availability, organization/product billing state, runner availability, workflow permission, and platform status before changing code. |
| Financial stop | Authoritative account evidence shows a budget, credit, spending-limit, or stop-usage control blocks execution | Record only the engineering impact; request the smallest account-holder action and do not expose balances, payment information, or account identifiers in the repository. |
| Credential or permission failure | Authentication or authorization fails at a defined boundary | Refresh short-lived identity when authorized, verify least-privilege scope, and never create a long-lived secret as a shortcut. |
| Azure service or policy failure | Azure returns a resource, policy, quota, identity, or regional error | Preserve the accepted state, avoid duplicate provisioning, use the approved resource group and cost boundary, and retry only after the cause is known. |
| Scheduling or process failure | The primary process is disabled, stale, or did not begin | Re-enable when safely authorized, verify a real subsequent start, and record the interruption if it affected progress. |
| External dependency failure | A required third-party service is unavailable or rate-limited | Continue independent work, preserve state, and retry later without broadening scope or weakening gates. |
| Governance inconsistency | GitHub evidence and continuity records disagree | Repair the continuity record from verifiable GitHub state through the controlled validation process. |

## 6. Recovery sequence

1. Preserve the last accepted application, database, traffic, DNS, identity, and frozen-release state.
2. Continue every safe independent workstream.
3. Choose the smallest reversible recovery action.
4. Retry only the failed or necessary job, workflow, or validation family when that provides valid evidence.
5. Avoid broad reruns, repeated Azure deployments, duplicate candidates, standing temporary resources, and speculative feature work.
6. If code or governed documentation changes, create a controlled validation branch and pull request.
7. Require the complete established gate set for the exact final candidate: deterministic reconstruction, SQLite, PostgreSQL 16, production container, dependency audit, Bandit, repository hygiene, Azure policy/infrastructure, CodeQL, and archived capability gates.
8. Close the controlled validation pull request without merge.
9. Advance the exact all-green head only by non-force fast-forward to the active development line.
10. Freeze or promote only through the separately governed release process.

## 7. Positive recovery confirmation

A setting change, saved budget, refreshed credential, retried workflow, or successful API response is not sufficient proof of recovery.

Recovery is confirmed only when the affected execution:

- actually begins;
- passes the previously blocked boundary;
- produces usable step or acceptance evidence;
- preserves the last accepted state and required controls; and
- updates the continuity record when authoritative state materially changes.

If recovery remains unverified, retain the blocker and its next bounded attempt.

## 8. Escalation

Escalate promptly when account-holder or human authority is required. The notice must state:

- the exact blocked outcome;
- the verified cause or the narrowest uncertainty;
- what safe work is continuing;
- the smallest specific action Marc must take;
- what evidence will confirm recovery; and
- whether any accepted release or demonstration state is at risk.

Do not ask Marc to send “continue.” Scheduled work resumes on the next permitted run.

## 9. Continuity record requirements

Record only non-sensitive engineering continuity information:

- current frozen release and commit;
- active development branch;
- active roadmap issue and bounded increment;
- last verified completed increment;
- candidate branch and controlled validation pull request;
- required gate state;
- genuine blocker, owner, and next bounded attempt;
- exact deployed demonstration release, commit, image digest, deployment time, workflow run, and acceptance result where applicable;
- next authorized increment; and
- date and 24-hour local time of the last verified update.

Never store credentials, secrets, payment data, account numbers, unnecessary balances, real Protected Member information, personal information, or investigation content.

## 10. Cost discipline

- Reuse valid acceptance evidence when the governed contract permits it.
- Do not repeat Azure deployments merely to check status.
- Prefer read-only checks before resource creation.
- Use bounded temporary resources and remove them after acceptance.
- Preserve immutable images and deterministic reconstruction.
- Do not provision paid GPU, vision, or other expensive optional services without explicit prior authorization.
- Cost savings must never weaken security, tenancy, recovery, rollback, source integrity, provenance, validation, or human authority.

## 11. Post-deployment application

After the first stable baseline, apply the same pattern to critical Salus recurring processes, including monitoring, reports, intelligence reviews, backups, recovery tests, deployments, integrations, and scheduled reassessments. Each critical process requires:

1. a defined heartbeat;
2. an independent watch where practical;
3. an authoritative state record;
4. a classified recovery path;
5. clear escalation ownership; and
6. positive confirmation that recovery succeeded.

## 12. Acceptance evidence

This SOP is accepted only after a controlled validation pull request passes every established required workflow family on its exact final head, closes without merge, and that exact head advances by non-force fast-forward to `development/salcapa-platform`. Issue #298 records the acceptance result.
