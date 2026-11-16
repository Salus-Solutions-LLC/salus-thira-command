# Salus Task Compliance and Assurance Standard

**Requirement:** SALUS-TASK-COMPLIANCE-001 / SAL-D138.
**Owner and verifier:** Salus assistant performing the task.
**Scope:** Each and every task and every type of work, including research, assessments, writing, code, document revision, communications, administration, planning, reviews, status checks and brief answers. There is no materiality, duration, repeat-task, internal-work or small-answer exemption.

## Accountability and human decisions

The assistant shall determine applicability, execute required work, inspect the resulting evidence, correct defects and verify compliance. Marc shall not be asked to certify that the assistant read sources, followed the Charter, completed checks or performed routine quality assurance. Produce the evidence and accurate disposition as part of the work. An assistant assertion, checklist tick, filename, passing unrelated test or count alone is insufficient.

Preserve separate human authority for consequential judgments/actions where the governing rule requires it, including final qualified findings or report issue, risk acceptance, sensitive disclosure, commercial commitments, purchases, protected exact-revision merges, deployments and operational implementation. An approval authorizes its named action/scope/version; it does not certify general compliance. A routine compliance record requires no additional human signoff. Do not create an approval loop to transfer the assistant's responsibility to Marc.

## Current authority and complete requirements accounting

At task start read the current Charter, Decision Register, approved artifacts, startup protocol and current handoff, plus applicable authorities and actual design artifacts. Compile/reconcile the governed source register with `tools/charter_task_compliance.py`. Its source coverage includes every nonblank line of the core authorities, this standard and agent instructions, then transitively discovered available backtick Markdown references. It preserves section/line locators, exact canonical UTF-8/LF content fingerprints, decision IDs and explicit unavailable/external/volatile references; it does not guess semantic applicability or silently omit unrecognized prose.

The generated `governance/charter_task_requirements_register.json` is the reproducible source-coverage index. The task's requirement record is the executable applicability and acceptance matrix. For each source unit determine whether it contains multiple obligations, context, history, a superseded rule or an applicable requirement. Decompose every applicable obligation into specific acceptance checks, with criterion, result and evidence references. Do not mark an entire multi-obligation paragraph met from one generic check. Context, nonapplicability and supersession require an explicit source-bound reason and evidence; supersession points to the controlling unit. This interpretive responsibility remains with the assistant; a parser cannot establish it.

Account for all units with met, not applicable, superseded, pending or blocked dispositions. Every met disposition requires evidence and passed acceptance checks. Retain all prior requirements and dispositions on reconciliation. Authority changes reopen checks and invalidate stale completion receipts; unchanged registry identity never proves evidence freshness. The volatile handoff and external/binary artifacts remain explicit references requiring task-specific resolution, not silently indexed as approved doctrine.

## Task lifecycle and continuity

Use one stable task identity within its authorized boundary. Before substantive work create a task record with objective, request/authorization, scope, source inventory, applicable requirements/checks, hold states, intended output claims, evidence locations, responsible verifier and pending human decisions. A bootstrap implementation must accurately record work predating the tool; do not fabricate a preflight timestamp. Initialization must not overwrite an existing task. Resume the same record after interruption/context loss; reconcile current authority before continuing.

Run verification at preflight, before changing a material claim, at handoff, after a scope/source/authority change, after correction and before every completion/release claim. Keep incomplete obligations visible during independent authorized work. A failed gate does not automatically authorize new access, spending, collection, research restart or production actions. If tools/records are unavailable, retain a blocked disposition and bounded progress report; never invent a passing result or silently exempt a short answer. This requirement applies even on surfaces without an executable checker; disclose unverified mechanical checks and maintain the same evidence record where authorized.

## Source coverage and source bibliography

Always perform the applicable SAL-D133 search and SAL-D116/SAL-D125 consideration process. Establish the complete current authorized Knowledge boundary and represented membership; account for all documents, versions, holds, extraction failures and available content. Reconcile before/after inventories with the current task-correlated review receipt. A prior task's receipt, ranked relevance query, metadata count, source-family screen, download list or historical baseline cannot stand in for current consideration. Do not reactivate the reader or replay consumed recovery activations to satisfy this rule.

Account for every OSINT Library source in the current authorized source inventory, its relevance and material linked records. Search the internet and relevant websites for supporting and contrary evidence and relevant concepts, strategies, methodologies, data, information and new ideas. Record actual queries, dates, publisher, title, exact URL, access date, version, portions reviewed, evidence/content status, relevance, where used and further linked-source obligations. Capture useful discoveries with provenance, limitations, rights and candidate/qualified/adopted disposition; explain why they change or do not change the task.

Keep discovered, searched, downloaded, metadata-screened, content-reviewed, inaccessible, held, excluded with reason and qualified states distinct. Relevant unavailable content is an open requirement, not a no-match. A topic-source inventory establishes the actual discovery boundary, not exhaustive knowledge of the internet. Refresh it as relevant sites or links emerge; record barriers and unfinished pursuit. Client citations and the restricted research/source register must reconcile before issue.

For other authorized locations, inventory/discover repositories, local records, attachments, prior chats/Pages, communications, approved artifacts and relevant connected sources. Search or record the exact unavailable boundary and decision effect. Preserve Protected Member isolation and current authorization. Never seek or publish another Member's records merely to fill a checklist.

## Evidence and outputs

Retain actual content/readback, tests, rendered-page review, source comparison, query/coverage receipts, approvals and outcome evidence in the appropriate authorized repository/engagement/knowledge zone. Give each proof an identity, provenance, verification method, exact version/hash, result and where-used link. Machine receipts must bind the task, authority register, evidence hashes and claim. Verify byte readback; restrict evidence paths to the authorized local root and reject changed/missing/foreign evidence. Metadata or self-attestation alone cannot prove substantive review, performance or visual acceptance.

For produced documents retain the current Charter visual standard, substantive-preservation check, exact editable/PDF identity, renderer, full page-count/review coverage, no open defects and accessible-structure checks. A subset of pages or stale artifact hash blocks a complete rendered-review claim. For code retain appropriate positive and adverse tests of actual behavior and the exact source checked. A code/CI pass is not production acceptance, corpus completion or substantive finding qualification.

Capture and reconcile available request, chat, files, decisions, research, changed/rejected ideas, outputs and verification under SAL-D134. Record expected versus retained items and destination/readback; unavailable full exports and historical gaps remain open. Keep identifiable Member material restricted; do not create a second Library copy of repository-backed source.

## Holds and human authority

Record exact task/reader/ingestion/operational holds and compare before/after evidence. The checker reads supplied records; it does not inspect or change live systems. A local assertion is not a fresh runtime audit. Preserve a paused assessment and disabled reader unless the user separately changes those instructions. Do not turn receipt of documents, a proposed review date, policy merge, code test or editorial correction into authority to resume an assessment or activate monitoring.

For each protected action retain the human authorization's source, actor role, exact action, target/scope/version and decision. Verify them separately from routine compliance. The checker can compare the recorded authorization to the intended action but cannot authenticate a person or grant permissions.

## Corrective action and claim gate

On failure, retain the error and open an assistant-owned corrective-action record identifying the missed requirement, cause analysis, affected work, correction, proof, retest and continuing impact. Reuse the stable task/error identity; preserve recurrence and previous dispositions. Diagnose the cause and identify affected artifacts before changing a rule or claiming closure. The engine automatically records fixed failure codes and retest history; the assistant supplies the actual cause/impact/treatment detail. Retest and verify applicable conditions before closure; never merely rewrite the failure as passed.

The local append journal uses atomic write/readback, an exclusive writer lock and a hash chain to detect accidental history edits. These are integrity checks, not cryptographic proof of an actor's honesty or a substitute for governed durable retention/backup. A failed write, lock conflict, stale register, missing evidence, membership drift, unresolved requirement or missing protected-action approval must fail closed.

Only a current verified record supports its bounded compliance claim. Keep control-package verification, research completeness, source qualification, report issue, human authorization and deployed enforcement separate. An incomplete receipt permits an accurate bounded progress/handoff statement, never “all requirements met,” “all sources reviewed” or a completed assessment. No unsupported percentage or universal compliance assertion.

## Implementation and verification boundary

The implementation consists of the source compiler, per-task initialization/reconciliation, evidence/coverage/output/hold/approval checker, corrective-action journal, private receipt, offline adverse-case tests, repository agent instructions and all-PR CI. CI checks the current committed register and tests; it does not inspect private Member task records or magically intercept every ChatGPT response. Branch-protection required-check installation, cross-workspace/platform interception, durable Library integration and production activation require their own authorized verified implementation. Do not claim these exist from this package.

Read `docs/charter-task-compliance.md` for commands and record formats. Operational task records and evidence stay outside the source repository. Add only member-neutral requirements and fictional tests here. This standard expands routine compliance/accounting to every task while preserving substantive human release/approval, lawful collection, source rights, privacy, cost limits, six-step methods and Charter formatting.

## Supporting research and limits

The NIST AI RMF Core (2023), MEASURE 1.1, 2.1, 2.3, 2.5 and MANAGE 4.3, supports recording test methods, conditions, limitations and improvement evidence: https://airc.nist.gov/airmf-resources/airmf/5-sec-core/ (reviewed 15 November 2026). It is a voluntary method reference, not a certification or evidence that these controls provide error-free performance. NIST also calls for independent expertise where appropriate; assistant self-checks do not replace required competent human judgments.


## Every-task model-switch reminder [SAL-D139]

Apply SALUS-MODEL-REMINDER-001 in the Charter before every task/brief answer and work-category change. Record task_type as assessment or other, then model_reminder with task_id, model, reasoning, text, evidence and automatic_switching_claimed=false. Assessment requires gpt-6-astra / highest_available; other requires gpt-6.1-sol / medium. Retain the exact visible user-facing reminder; normalized text and its actual evidence bytes must contain the required model and reasoning request. The checker verifies the recorded reminder and its bytes, not actual delivery to a person, semantic task classification, actual model selection or universal cross-chat interception. The assistant must classify the task honestly and issue the reminder visibly. A missing/unclassified task, foreign reminder, absent evidence, mismatched model/reasoning/text or automatic-switch claim blocks record verification and enters corrective-action tracking. No new human attestation or reminder-acknowledgement gate is created; existing source/capture/quality and protected-action gates remain unchanged.

Retained reminder evidence is JSON containing task_id and visible_text copied from the actual user-facing reminder, with its source reference/provenance. Its task identity and normalized exact text must match the current reminder record; another task's reminder or malformed evidence cannot satisfy the check. This binding does not establish delivery or selected-model truth without separate actual evidence.
