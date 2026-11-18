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

### Research entry for an assessment

Classify the assessment with `--task-type assessment` at initialization. Its
start time belongs to the new task. Preserve any genuine existing start and
earlier records when resuming. If prior research timing cannot be established,
record that limitation and open a prospective review of the affected decision.
Keep all identifying information and execution receipts in authorized private
storage outside this checkout. The offline example in
`tools/test_assessment_research_entry.py` uses fictional data only.

First bind the commissioning request, the Member and locality, relevant official
domains and aliases, related authorities, and required source identities to
the scope receipt. Then populate the four location inventories and original
source dispositions. The research receipt maps those locations to the four
SAL-D075 reporting streams and identifies actual queries and retained evidence.
For each required original, identify the relevant passage and its decision
effect. Record search boundaries, contradictory and superseding material,
and decision-changing gaps. A required source that cannot be inspected keeps
the affected assessment in candidate status.

When the request uses shorthand, retain the actual phrase in `requested_as`
and bind its resolution to the canonical original, identifying passage, version
and source location. If an entity has no identifiable public site, keep its
identity evidence and the executed name, alias and jurisdiction searches.
Use `website_gaps` only when their bounds and effect support a non-decisive
no-find. A missing decision-changing record remains open.

Set the scope and research evidence IDs in `assessment_research`. Before
the first substantive assessment output run the following command with a fresh
receipt path. Retain earlier attempts and use the same task journal throughout.

```text
python tools/charter_task_compliance.py research-entry --root . --register governance/charter_task_requirements_register.json --task PRIVATE/task.json --evidence-root PRIVATE/evidence --receipt PRIVATE/evidence/research-entry-1.json --journal PRIVATE/corrective-actions.json
```

`candidate_only` and exit status 2 identify open evidence. Continue source
work and correct or carry the gaps. A successful `entry_verified` receipt
permits the substantive assessment within its recorded scope. Register the
exact receipt bytes as private task evidence and set `assessment_entry_receipt`
to that evidence ID. In `assessment_research.analysis`, reference the subsequent
first-analysis record and its actual work product. Run the ordinary `verify`
command against the same journal before any completion claim. The verifier
checks the entry event, its authority and four review bindings, and that analysis
follows the entry. If material new evidence changes a decision, preserve the
earlier edition and create a new prospective review of the affected conclusions
under the engagement. Incomplete historical work cannot be backdated.

The offline verifier can correlate local evidence, recorded times and journal
order. Independent source provenance and protected record custody remain
necessary to substantiate when real work occurred. The verifier cannot discover
an unrecorded request, alias, publication or partner relationship, detect
off-record analysis, authenticate an author, or establish that a searched site
was complete. Compare the scope with the original instructions and newly
discovered sources before accepting the assessment. This control grants no
source access and performs no network retrieval or publication.

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



## Model reminders on every task [SAL-D139]

Before work, issue the visible Charter reminder and retain its exact text/evidence. Use --task-type assessment or --task-type other with init; omitted classification remains unclassified and cannot pass. Task records created before this requirement must explicitly add classification and the current task's reminder on resumption; reconcile authority changes without inventing historical reminders. Assessment-specific research, analysis and reports are assessment work; general governance, status and software tasks are other work. Mixed work requires new reminders when categories change and when switching back.

Set task.model_reminder to task_id, model, reasoning, text, evidence IDs and automatic_switching_claimed=false. Valid pairs are assessment/gpt-6.2-astra/highest_available and other/gpt-6.1-sol/medium. Reminder text and its retained evidence must name GPT-6.2 Astra plus highest available reasoning, or GPT-6.1 Sol plus Medium reasoning. Preserve exact user-visible wording; typography normalization tolerates Markdown bold and common hyphen variants. Record proof of the reminder; do not assert an actual model switch or universal routing. Missing/unclassified or mismatched reminders fail the evidence gate. The checker does not determine task meaning or interrogate the model selector; the assistant remains responsible. Issuing a reminder creates no acknowledgement gate and cannot resume Compass or enable its reader.

Retained reminder evidence is JSON containing task_id and visible_text copied from the actual user-facing reminder, with its source reference/provenance. Its task identity and normalized exact text must match the current reminder record; another task's reminder or malformed evidence cannot satisfy the check. This binding does not establish delivery or selected-model truth without separate actual evidence.


## Every-task analytical assurance [SAL-D143]

Initialization creates an empty analytical_review map, never passing analysis. Populate exactly assumptions, methodologies, evidence_and_consequences and recommendations for every task. Each has state=reviewed, conclusion, reasoning, limitations (nonempty list) and evidence IDs. Its retained JSON review evidence binds task_id and lens to the identical conclusion/reasoning/limitations. Supply actual supporting source, comparison, test and decision evidence in addition to the review record. A matching summary is not proof of semantic truth. Missing duties, empty fields, blanket not-applicable, foreign task/lens evidence, malformed proof and conclusion mismatches fail closed. See `SALUS_ANALYTICAL_ASSUMPTIONS_TO_ACTION_STANDARD.md` for the substantive analytical method.

Review depth is proportionate; no task is exempt. Explain a bounded no-conflict or no-applicable-alternative finding and the review performed when appropriate, without inventing one. Preserve evidence gaps and their consequences. Reconcile authority changes, retain previous review/evidence and recheck assumptions, methods, contradictions, consequences and recommendations before closeout. Routine verification belongs to the assistant; consequential human decisions remain separate. SAL-D142 updates only the assessment model reminder to GPT-6.2 Astra at highest available reasoning; other work stays GPT-6.1 Sol Medium. Model selection, runtime, Compass pause and reader controls are unchanged.

## Recording re-passes and the final editorial pass [SAL-D144]

Record the initial work or its evidence identity before reviewing it. Keep an ordered `review_passes` record of at least eight substantive re-passes followed by at least one separate editorial pass. Give each substantive entry a specific question, the actual supporting evidence, the observed result, and the action taken or reason to retain the work. On a short answer, these may be concise checks of the working answer. On a non-document task, the final response or handoff is the editorial review target.

Each entry has `kind` (`substantive` or `editorial`), `focus`, `finding`, `disposition`, a nonempty `reviewed` list of evidence IDs and an `evidence` list containing one unique pass receipt ID. In that receipt, record `task_id`, the one-based integer `sequence`, the matching kind, focus, finding and disposition, and a `reviewed_sha256` mapping from each reviewed ID to its verified digest. Each `reviewed` list includes the exact work product, intermediate decision or draft answer examined. Add source and test evidence as needed. The final editorial pass covers every outgoing item in `outputs`. Include the retained response, decision or handoff there when the work produces no file for delivery.

For example, a substantive pass can trace a stated deadline to its original record and correct the case to which it applies. A later editorial pass can check that an unfamiliar reader sees the correct deadline and responsible role in the final text. Each entry points to evidence from that work. Recheck affected findings and repeat editorial review after a material change. Record missing or stale work as incomplete until corrected.
