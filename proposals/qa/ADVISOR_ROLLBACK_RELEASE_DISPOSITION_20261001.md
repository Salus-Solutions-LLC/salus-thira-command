# Protection Advisor and rollback release disposition — 01 October 2026

**Status:** Internal, Member-neutral release review record. This is not an issued offer, Member report, or production acceptance.

## 02 October 2026 addendum — accepted worker execution failure

Live Azure execution history and direct logs established that the accepted `3.202` scheduled knowledge worker is failing with an uncaught `zipfile.BadZipFile` when a damaged Office package passes the ZIP end-record probe but fails central-directory parsing. The latest 20 executions displayed at discovery were all Failed; the trace was obtained from execution `salcapa-dev-b48224-kb-scan-29848406`. No source identity or contents are reproduced here. The worker's accepted image and two-minute schedule are present, but **worker health is not an accepted baseline**. The environment now has Marc-approved console/system diagnostics routed to the existing Log Analytics workspace; direct execution logs supplied the trace, while workspace ingestion still needs verification.

Draft head `d77dc9ff6b9ca469b66d4fc1a5a3217764cad23b` translates damaged ZIP central-directory and part-read failures into `DOCUMENT_PACKAGE_INVALID` per-source processing failures and adds a synthetic regression to the package CI. Public Protection Advisor run 568, SalCAPA Analytical Actions run 24 and Salus package rollout run 185 passed, including the Office regression and Windows/report and PostgreSQL jobs. No immutable image, qualified review, Azure worker repair, live Advisor or intake acceptance follows from these tests. Before promotion, prove the corrected worker on a bounded execution, schedule continuity, no overlap and failed-promotion restoration. The original release decision below remains **Hold activation and public claims**.

## Exact identities and evidence

- Accepted application and scheduled knowledge-worker image: `release/v3.202`, source `1268a9d951fab77229659dff6530dd96eadb943b`, digest `salcapadevb48224acr.azurecr.io/salcapa@sha256:77b9ecd15c25a5baad55be47a6385429df3eb9c3f5712a0cd94745d22cf6f8b1`. A signed-in Azure portal read showed this digest on both resources; it did not test worker execution.
- Current draft PR #589 head: `fe58de5bea52db321fa64e479aa67d44103c36dc`. Source correction: `46b6373ae475d62c95ebb768735f9dbced74133b`. The draft app declares candidate `3.203`; no `release/v3.203` tag, immutable candidate image or activation exists.
- Exact-head GitHub checks passed: Public Protection Advisor run 557, SalCAPA Analytical Actions run 13, and Salus package rollout run 174. The package check compiles the application Bicep and validates protected workflow shell syntax. These are source checks, not an Azure failure-injection or live browser result.
- The draft PR is open and marked draft, with no submitted review. Relative to the accepted `release/v3.202` source, it changes 124 files with approximately 17,000 insertions. This is not a narrow rollback-only patch.
- The earlier manual-trigger correction at draft commit `ea343bf8dbcd4566060d7608661a6d71fc97566e` is superseded. The candidate-image execution override is exact draft commit `829297d58228e9cf619b8fcec2ad471309da77e5`. Public Protection Advisor run 560, SalCAPA Analytical Actions run 16 and Salus package rollout run 177 all passed for that exact head. The package check verifies the one-off-before-promotion ordering, Bicep compilation and workflow shell syntax. Azure behavior and forced-failure rollback remain untested.

## Release decision

**Hold activation and public claims.** The independent application/worker rollback and staged worker promotion are corrected in draft source, but neither a forced-failure rollback nor a `3.203` deployment has run in Azure. A further draft correction starts one candidate-image execution with an image override while the accepted scheduled job keeps its accepted image and two-minute schedule. It checks the execution's actual image and success, rechecks the accepted job, and only then updates the scheduled job to the candidate image. The failure path restores the accepted image and schedule. The protected operator must validate this one-off override and any overlapping execution in Azure, then run the governed what-if, failure-path and rollback evidence before accepting the release.

**Additional no-overlap gate:** The accepted knowledge processor's non-bulk path has no batch-wide lease. A one-off candidate execution can run concurrently with a scheduled accepted execution and process the same pending files. No live overlap has been attempted. Before activation, engineering must prove a no-overlap promotion sequence or an isolated candidate fixture, with test evidence; ordinary source CI and the execution-image check do not close this gate.

**Controlled correction under review:** The draft workflow now pauses new scheduled starts by switching the accepted-image job to Manual, drains observed active executions, runs and verifies the candidate execution, then resumes the two-minute schedule with the candidate image. Failure restoration returns to the accepted image and schedule. This trades a bounded release maintenance interval for avoiding simultaneous accepted/candidate scans; Azure trigger propagation, execution listing and an outside manual start still require protected live validation. The accepted live job has not been paused.

The no-overlap correction is exact draft source `33d07272829af30a2c1d584bc8b78e0d2cc7448b`. Public Protection Advisor run 563, SalCAPA Analytical Actions run 19 and package rollout run 180 passed for that source. These checks verify source ordering and compilation; they are not Azure behavior or failure-injection proof.

The revised Protection Advisor Part 1 and Part 2 and the Level 1 intake remain candidate material. Published Wix explanatory copy does not publish the revised application. The current application keeps package commerce disabled; scanner-backed uploads remain gated. Do not invite Member files, purchase, or protected-account creation through the preview.

## Required exact-version dispositions

| Item | Evidence now | Required disposition before issue |
|---|---|---|
| Code and rollback | Draft source and exact-head CI pass | Qualified review of the complete frozen delta, immutable image and activation; Azure staged worker and forced-failure rollback evidence |
| Part 1 and Part 2 | Local Word candidates and source tests | Exact binary, accessibility, privacy, web/PDF/print parity, nonexpert and live anonymous/authenticated browser review |
| Level 1 intake | Candidate questions, receipt/quote workflow and upload gate | Approved agreement and scope link, tailored staged questions, live scanner/quarantine/alerts/retention and Member/Salus role tests |
| Public communication | Wix explanatory copy published and desktop read back | Mobile and assistive-technology check; distinguish the current live form from the candidate |

**Owner and next action:** Engineering prepares a frozen, smaller release boundary where feasible and runs the protected acceptance sequence. The qualified product/document/release reviewer records exact-version determinations. Marc's broad authorization to finish and publish is already recorded; this record does not ask him to repeat it. If the gates remain open at the 02 October afternoon Central Time demo, show the labeled fictional preview and verified live `3.202` behavior only.
