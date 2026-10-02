# Protection Advisor and rollback release disposition — 01 October 2026

**Status:** Internal, Member-neutral release review record. This is not an issued offer, Member report, or production acceptance.

## Exact identities and evidence

- Accepted application and scheduled knowledge-worker image: `release/v3.202`, source `1268a9d951fab77229659dff6530dd96eadb943b`, digest `salcapadevb48224acr.azurecr.io/salcapa@sha256:77b9ecd15c25a5baad55be47a6385429df3eb9c3f5712a0cd94745d22cf6f8b1`. A signed-in Azure portal read showed this digest on both resources; it did not test worker execution.
- Current draft PR #589 head: `fe58de5bea52db321fa64e479aa67d44103c36dc`. Source correction: `46b6373ae475d62c95ebb768735f9dbced74133b`. The draft app declares candidate `3.203`; no `release/v3.203` tag, immutable candidate image or activation exists.
- Exact-head GitHub checks passed: Public Protection Advisor run 557, SalCAPA Analytical Actions run 13, and Salus package rollout run 174. The package check compiles the application Bicep and validates protected workflow shell syntax. These are source checks, not an Azure failure-injection or live browser result.
- The draft PR is open and marked draft, with no submitted review. Relative to the accepted `release/v3.202` source, it changes 124 files with approximately 17,000 insertions. This is not a narrow rollback-only patch.
- The manual-trigger correction is exact draft commit `ea343bf8dbcd4566060d7608661a6d71fc97566e`. Public Protection Advisor run 558, SalCAPA Analytical Actions run 14 and Salus package rollout run 175 all passed for that head. The package run checks manual-test-before-schedule order and rollback schedule restoration; it cannot prove Azure accepts the transition or that an already-running execution is unaffected.

## Release decision

**Hold activation and public claims.** The independent application/worker rollback and staged worker promotion are corrected in draft source, but neither a forced-failure rollback nor a `3.203` deployment has run in Azure. A further draft correction changes the worker to a manual trigger while the candidate image is tested, then restores the two-minute schedule only after that execution succeeds; the failure path restores both the accepted image and schedule. The protected operator must validate this trigger transition and any running execution during an actual promotion, then run the governed what-if, failure-path and rollback evidence before accepting the release.

The revised Protection Advisor Part 1 and Part 2 and the Level 1 intake remain candidate material. Published Wix explanatory copy does not publish the revised application. The current application keeps package commerce disabled; scanner-backed uploads remain gated. Do not invite Member files, purchase, or protected-account creation through the preview.

## Required exact-version dispositions

| Item | Evidence now | Required disposition before issue |
|---|---|---|
| Code and rollback | Draft source and exact-head CI pass | Qualified review of the complete frozen delta, immutable image and activation; Azure staged worker and forced-failure rollback evidence |
| Part 1 and Part 2 | Local Word candidates and source tests | Exact binary, accessibility, privacy, web/PDF/print parity, nonexpert and live anonymous/authenticated browser review |
| Level 1 intake | Candidate questions, receipt/quote workflow and upload gate | Approved agreement and scope link, tailored staged questions, live scanner/quarantine/alerts/retention and Member/Salus role tests |
| Public communication | Wix explanatory copy published and desktop read back | Mobile and assistive-technology check; distinguish the current live form from the candidate |

**Owner and next action:** Engineering prepares a frozen, smaller release boundary where feasible and runs the protected acceptance sequence. The qualified product/document/release reviewer records exact-version determinations. Marc's broad authorization to finish and publish is already recorded; this record does not ask him to repeat it. If the gates remain open at the 02 October afternoon Central Time demo, show the labeled fictional preview and verified live `3.202` behavior only.
