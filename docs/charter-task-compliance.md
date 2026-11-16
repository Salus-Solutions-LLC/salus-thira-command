# Every-task compliance assurance runbook

Controlled implementation candidate for SAL-D138 / SALUS-TASK-COMPLIANCE-001.
The governing standard is `SALUS_TASK_COMPLIANCE_ASSURANCE_STANDARD.md`.
This is an operational control description, not an issued client report.

## Start and resume

For every task, inspect current authority and the actual applicable artifacts.
Record the five-part startup summary before mutation. Identify the exact authorized
boundary, output claim and current holds. Do not reset an existing task to erase
failures. The bootstrap implementation must identify any work that preceded its
creation; never manufacture a preflight timestamp.

Run with Python 3.12 or later from the governed checkout. Substitute an authorized
restricted record directory outside the checkout for PRIVATE. Do not commit task
evidence, Protected Member information, credentials or private error receipts.

```text
python tools/charter_task_compliance.py register --root . --register governance/charter_task_requirements_register.json
python tools/ci_charter_task_compliance.py
python tools/charter_task_compliance.py init --root . --register governance/charter_task_requirements_register.json --task PRIVATE/task.json --task-id STABLE-ID --objective "Authorized objective"
python tools/charter_task_compliance.py reconcile --root . --register governance/charter_task_requirements_register.json --task PRIVATE/task.json
python tools/charter_task_compliance.py verify --root . --register governance/charter_task_requirements_register.json --task PRIVATE/task.json --evidence-root PRIVATE/evidence --receipt PRIVATE/receipt.json --journal PRIVATE/corrective-actions.json
python -m unittest discover -s tests -p test_charter_task_compliance.py -v
```

Initialization creates pending requirements, never a passing task. Reconciliation
archives prior dispositions and reopens requirements after authority changes.
The generated register indexes every nonblank line of roots and available
backtick-referenced Markdown files, preserving headings, context and history.
It does not infer individual semantic obligations. Decompose compound obligations
into named acceptance checks; justify applicability and supersession against
current authority. Unexpanded, binary, external and volatile references require
explicit task-specific resolution. A generated index is not evidence of review.

## Task and evidence fields

`scope` records authorization, boundary and limitations. Each requirements row has
id, state, reason, evidence IDs and checks. States are met, not_applicable,
superseded, pending or blocked. A met row requires passed checks containing
criterion, result and evidence. Supersession identifies another catalog unit.
Unexpanded references require resolved/not_applicable, reason and evidence.

Evidence is a map from stable IDs to path, sha256, provenance, method and result.
Paths are relative to evidence-root; traversal, foreign drives and symlink escapes
are rejected. The checker reads actual bytes and requires verified results.
Attestation, filename and metadata_only methods cannot stand alone as proof.
The assistant must inspect actual content and meaning; hashes cannot do that.

`locations` contains knowledge, osint, internet and other_authorized_locations.
Each has state=considered, boundary, discovery_method, evidence IDs and before,
after and review evidence IDs. Inventory JSON contains task_id, boundary,
observed_at (timezone required), authority and items with id/version. Before and
after membership must agree exactly. Refresh changed inventories; a snapshot
older than 24 hours or in the future blocks verification. Review JSON contains
the same task_id and exactly the inventory membership, each with id/version,
state, relevant, reason, evidence, portion_reviewed and where_used. A relevant
unavailable item is an open gap. An empty discovery boundary needs real proof of
the boundary; it is not permission to omit a location. Internet additionally
requires actual queries with query/searched_at/evidence, and source records with
exact url, publisher, title and accessed_at. Retain supporting and contrary
findings and new ideas, not merely download or source counts.

`capture` requires state=reconciled, expected/retained counts, destination and
evidence. Counts must cover the actual available request/chat/research/decision
boundary and cannot be invented to force equality. A partial chat export is a gap.

`holds` binds expected state to before_evidence and after_evidence of actual
readbacks. The checker compares records; it does not interrogate production.
The assistant must validate current authorization and actual hold state.
Compass remains paused and the reader disabled; no verification run restarts them.

`outputs` lists exact artifact evidence, claim, format and verification_evidence.
For docx/pdf/pptx, page_review points to JSON binding artifact_sha256, pages,
reviewed_pages (all 1 through N) and defects_open=0. Accessibility, content
preservation, OPM-referenced Charter style, full-size page inspection and offered
format parity remain substantive checks; do not claim them from page numbers.

`protected_actions` requires actual human approval evidence with actor_role=human,
decision=authorized, action, exact target and source_reference. A receipt matches
recorded scope; it does not authenticate a person's identity. The assistant
verifies the underlying approval before action. Routine compliance verification
belongs to the assistant and never requires Marc's attestation.

## Failure, correction and closeout

Exit 0 means verified_record for the supplied record and bytes, not universal
semantic compliance or production acceptance. Exit 2 means incomplete; exit 1
means invalid/unavailable. Aggregate stdout avoids source disclosure. Restricted
receipts retain exact error codes, authority/task/evidence hashes and boundaries.

Every failure creates or reopens a stable corrective-action ID in the task journal.
For correction, add task.corrective_actions entries with id, cause, affected_work,
correction and evidence IDs. Retest the entire current record; missing cause,
impact, treatment or verified proof leaves the correction open even after a clean
current check. Preserve history, do not rewrite the prior failure. An exclusive
lock rejects concurrent writers; an interrupted stale lock requires investigation,
not blind deletion. Atomic save and readback detect failed writes. Journal hashes
detect accidental edits, not malicious rewriting or cryptographic authenticity.

Run at startup, continuation, correction, handoff and before a completion claim.
Retain incomplete obligations while doing independent authorized work; no automatic
waiver or access expansion. Full current corpus/capture proof unavailable means a
full compliance claim remains blocked. Bounded software-test outcomes may still be
reported precisely. Record the gap, impact, owner, next action and authority.

## Integration and acceptance limits

CI runs on every pull request and governed-branch push without path filters,
write permissions, secrets or production actions. It checks register freshness
and offline control tests. It does not obtain task records, require human routine
attestation, configure branch protection or prove any task reviewed a corpus.
Branch protection, deployed Library service integration and interception of all
ChatGPT surfaces are not installed by these files. No local success establishes
universal platform enforcement. The universal behavioral requirement still applies.

Test fixtures are fictional. Never put actual task receipts or Member details in
CI. Preserve protected release rules, Compass pause, disabled reader and unrelated
recovery work. See the standard for source-research provenance and limitations.

