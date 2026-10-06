---
schema_version: 1
record_kind: salcapa_build_continuity
last_verified_at: 06 October 2026 11:23 CDT
current_frozen_release: v3.218
current_frozen_commit: b6092778f2fdc79c23e43ef998ce8f155a2f225e
active_development_branch: development/salcapa-platform
current_development_head: 6b2737195a21ef767ad2d5c72d688610e7179f71
active_product_milestone: issue_520_dependable_governed_intake
active_build_system_issue: 520
active_increment: salus_v3218_customer_issuer_application_promotion
last_completed_increment: v3218_immutable_image_published_and_read_back
candidate_release: v3.218
validation_pr: 741
validation_branch: candidate/level1a-v3218-app-20261006
validation_base: development/salcapa-platform
validation_head: pending_exact_candidate_commit
validation_gate_state: controlled_validation_in_progress
failed_workflows: v3216_full_ci_failed_stale_workforce_signin_smoke
first_root_failing_gate: v3216_passwordless_runtime_secret_paths
root_cause: stale_workforce_signin_button_copy_assertion
repair_head: 3b87801620f2ec875ac37021ad08aabb0266ce34
repair_summary: v3217_preserves_both_signin_destinations_without_label_binding
genuine_blockers: v3216_superseded_before_publication_member_upload_quote_checkout_closed
next_authorized_step: review_exact_v3218_application_record_and_azure_preview_before_protected_deployment
deployed_demo_release: v3.217
deployed_demo_state: protected_v3217_deployment_verified_level1a_member_controls_closed
---

# SalCAPA build continuity

This non-sensitive engineering record is the restart point for the unified SalCAPA build.

## Current controlled checkpoint

v3218_customer_issuer_image_published: Marc approved PR #740 at exact head `a11e4c596a7e1dec0d0866b68a4478890764d3d6` after all 18 candidate workflows and full frozen v3.218 release CI passed. It merged as `6b2737195a21ef767ad2d5c72d688610e7179f71`. Protected image run `37494721622` succeeded and read back `salcapadevb48224acr.azurecr.io/salcapa@sha256:528d4c475aa2540fbdbed998a066aca00ee800a2fc61ab351a8c9c82882f6887` for frozen commit `b6092778f2fdc79c23e43ef998ce8f155a2f225e`. A separate application candidate pins that digest and retains accepted v3.217 as rollback; its checks, Azure preview, exact-head review and deployment remain open. Serving Advisor remains v3.217, and buyer sign-in, Level 1A purchase/intake/upload switches remain off. Real customer token claims, Stripe, approved Word issue, receipt, scanner-backed upload and Wix acceptance are unproved.

v3218_customer_issuer_image_candidate: Marc reviewed PR #739 at exact head `dd5241fc0c28540a14df962375203902fdb33bff` after all 20 candidate workflows passed; it merged as `b6092778f2fdc79c23e43ef998ce8f155a2f225e`. `release/v3.218` was created at that exact commit, and its Release Branch Guard passed. Full frozen-release CI and contextual intake checks were still running when this candidate was prepared. This record stages one immutable image from the frozen source after those checks and a separate exact-head review. It does not deploy the application, enable buyer sign-in, open commerce or upload files. Serving app and accepted Advisor remain v3.217; signed buyer token, cross-tenant denial, Stripe, approved Word issue, receipt, scanner-backed intake and Wix checks are unproved.

v3218_customer_issuer_source_candidate: Marc exact-reviewed PR #738 head `b7b4f9f72604cb4d206311c0a84c7372b231086e` after all four candidate check groups passed; it merged as `61d427cb9b337dbe5cad5b8cd0dd33eb5c327106`. The repair pins the customer issuer hostname returned by the live public External ID discovery document while retaining the separately pinned authorization, token and JWKS hostname. A v3.218 runtime-label candidate is staged; it has not been frozen, built or deployed. The accepted public Advisor remains v3.217. Actual buyer ID-token claims, certificate retrieval, billing linkage, cross-tenant denial, Stripe payment, agreement issue, receipt and scanner-backed upload remain unproved; all public buyer and Level 1A purchase/intake/upload controls remain closed.

v3217_buyer_identity_application_deployed: Marc reviewed PR #735 exact head `8ef619f08b285dbdf8b486cbff368aaae16b213e` after all 19 candidate workflows passed. It merged as `677921f720e1a4d764117e665fb9a75e6dcca421`. Protected application run `37466765814` succeeded. Azure preview reported 21 modifications, 3 no-change and 18 ignored resources, with no creation or deletion. The run verified the exact v3.217 image, readiness, workforce sign-in configuration, isolated Microsoft 365 intake, a fictional public Protection Advisor journey and the scheduled knowledge worker. The accepted rollback recorded by this deployment is the previously running v3.215 image. Marc accepted the exact live v3.217 Advisor output; handoff PR #737 recorded that determination and merged as `9260c7e6f5e33071ba4371f0666a250c50651b61`. This does not prove customer External ID token claims, Stripe payment, Word issue, immutable receipt or scanner-backed Member upload; public buyer sign-in and Level 1A commerce/intake/upload controls remain closed.

v3217_buyer_identity_image_published: Marc approved PR #734 exact head `6a58042a9454eec251577866d3b7b66ac9f7aa89` after all 18 candidate workflows passed. It merged as `e0e84a84a3258611306a2febb7209a988e3564d4`. Protected image run `37465219982` succeeded and read back `salcapadevb48224acr.azurecr.io/salcapa@sha256:fdcc5d5868f3b35e1bb6c2b615c1ea3cc79f4552804693daaa0b14f587582485` for frozen source `1b0e972946337a45aa4e8b0ec4360913bfbc2779`. The application deployment record is a separate candidate and retains the currently running v3.215 image as operational rollback; v3.215 has a successful protected deployment but its exact live output remains unaccepted. Qualified v3.210 remains an older registry fallback. Serving app remains v3.215; public buyer sign-in, quote, Checkout, payment, receipt, intake and Member uploads remain closed pending protected deployment and separate live acceptance.

v3217_buyer_identity_image_candidate: Marc reviewed PR #733 at `3b87801620f2ec875ac37021ad08aabb0266ce34`; both PR checks passed and it merged as `1b0e972946337a45aa4e8b0ec4360913bfbc2779`. The `release/v3.217` branch guard, full release CI run `37463667613`, and contextual intake run `37463667710` succeeded. The only source repair removes an obsolete visible-label assertion while retaining checks of the exact workforce and buyer sign-in destinations. This candidate binds the immutable image to the exact frozen v3.217 commit; deployed app v3.215 and v3.210 rollback remain unchanged. Public sign-in, quote, Checkout, payment, receipt, intake and Member uploads remain closed pending live proof and qualified output review.

v3216_superseded_before_publication: Marc reviewed PR #731 at `1be8d1069968cc06f3b3bd15d3970b783fa92c11`; both PR checks passed and it merged as `807b2892042d83a9e3f13e0e87eb10eeffe65941`. The release/v3.216 branch guard succeeded, but full release CI run `37461798530` failed because a passwordless smoke test still required the old visible workforce sign-in button text. The app now labels that same route `Salus and existing Member sign-in` and also provides a separate customer button behind closed controls. No v3.216 image was published; image PR #732 closed unmerged. A narrow test repair and v3.217 runtime identity are candidates. The deployed v3.215 app and v3.210 rollback remain unchanged; Member quote, Checkout, payment, receipt, intake and uploads stay closed.

v3215_level1a_image_candidate: Reviewed PR #717 at `375e1b895f58bbf84efffc3d0c22fa95f7d571d2` merged as `5d531157db1e920dd7c4b6c19446d3f273745df9` and froze release/v3.215 at that exact commit. The immutable-release guard passed; its development continuity check failed because the record still named v3.214, which this candidate corrects. The approved Level 1A rev10 Word template was uploaded to the private evidence container, read back byte-for-byte at SHA-256 `63AD42DADC81A054FA28EF55EAADC8DFBD10C9CA983AB81C2D085E033F046CF6`, and the temporary human Blob role was removed. Draft PR #718 stages only a protected v3.215 image record and an exact bounded lineage check. Accepted public app remains v3.210. Member quotes, checkout, payment, upload and receipts remain closed until separate protected deployment and end-to-end acceptance. Do not infer publication or stability from source checks or the template upload.

v3213_scanner_clean_event_shape_failed: The v3.213 scheduled scanner worker processed the fictional EICAR result as Malicious but repeatedly held the original fictional Clean event Pending. One-time read-only classifiers found exactly one ledger candidate with matching topic, event type, URI and canonical ETag, a valid recorded SHA-256, and a Clean result with no result-details object or event digest. Marc exact-reviewed PR #706 at `44414ab5194a8a335bb790c6ead9f7153826a805`; all three source test groups passed, including the PostgreSQL intake path, and it merged as `8df81351fe3a32863739574c352c4f9c0b4138c0`. Reviewed PR #707 froze v3.214 at `04b6e6ae47e83dcab9d5c76edb56f95327f1a7fc` after its analytical and package checks. The candidate image is for the scheduled scanner worker only; accepted public app remains v3.210 and current scanner worker remains v3.213 pending separate protected promotion. The v3.213 image remains the worker rollback. Do not claim Clean promotion from code tests. Govern the image readback, exact worker change, original fictional named-version result, adverse hold, real Fired alert email/recovery and qualified live review before opening Member uploads; quote, checkout, purchases and receipts remain closed.

v3212_private_scanner_acceptance_failed: The private fictional Clean/EICAR run on the published v3.212 image timed out with both exact Blob versions Pending. Settled probes found base64-wrapped Event Grid queue messages, one-pair ETag quotation differences, and no SHA-256 field on the Clean event. Reviewed PR #695 merged the narrow fail-closed repair as `bd8e1e9beb56086d8529028309c96a6874ef74bc`; reviewed PR #697 froze v3.213 source at `7ec414abe94092e631f0a4b7222fd99ce34b7e26`. The v3.212 image was published for private testing but not accepted for Member uploads or deployed as the application. Accepted live application v3.210 and its rollback remain unchanged. The v3.213 image record is a candidate: exact-head checks, qualified review, protected image readback, guarded scanner-worker deployment, independent fictional Clean/EICAR exact-version outcomes, real alert and recovery proof, commercial/OIDC/Stripe tests, and qualified release are still open. Do not rerun the already used one-time private job. Member uploads, quotes, checkout, purchases and receipts remain closed.

v3211_superseded_before_publication: Frozen v3.211 at `c2b83cdc8cd7f45f868de9eeeffbf1fb9f4489ac` passed its branch guard, but its private manual scanner acceptance job name was 34 characters. Azure's Container Apps Job name rule requires fewer than 32. Draft image PR #666 was closed unmerged before any image or Azure job deployment. Candidate v3.212 at frozen source `7867fa72ae404aa5ed37abd104ecc1c69b9ea190` shortens the job name to 28 characters and adds cross-file regression checks. Accepted app v3.210 remains live; Member uploads, quotes, checkout, purchases and receipts remain closed. PR #668 stages image publication only, subject to exact-head checks and Marc's review. Private Azure what-if, identity/cost, Clean/EICAR exact-object, real alert and commercial/OIDC/payment gates remain separate.

Historical checkpoint (superseded by the v3.210 live approval above): the accepted development application was v3.208 at frozen source `9517d5a3d8ff03ed8e8311f86a34485e16a85ec0` and immutable digest `sha256:0936238597e51f13138d9121724328d170ab71000693b5bde4272456d320b966`. Protected [image run 37089024553](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/37089024553) and [application run 37089539089](https://github.com/Salus-Solutions-LLC/salus-thira-command/actions/runs/37089539089) succeeded. Independent Azure readback showed app revision `salcapa-dev-b48224--0000147` at 100% traffic and the scheduled knowledge job on that digest; its isolated acceptance execution succeeded. Marc approved the exact live 3.208 app and Advisor output. The standing five-minute scanner-result job still used v3.206 at that readback; Member upload, quote, and purchase controls remain closed. Large-batch issue #520 remains paused. The following paragraphs preserve earlier checkpoints as history.

The v3.197 candidate routes the existing Salus pending folder through the durable bulk worker with an exact, live-verified customer staging sibling and a two-minute schedule. PR #542 exact head `f5a7822da16afc97e24f8d179bd26285ff789899` passed CI, CodeQL, contextual intake, and Azure infrastructure validation before closing without merge; its four tested file blobs were advanced with a non-force development commit `623b94b79469ff1f0b0cbd66b05e9fcb00332b37`. Runtime marker advanced to 3.197 at `892d993702a44376fca3830adcc2cbb662b76dd9`. The first development continuity job failed solely because this record still named candidate v3.196. This update repairs the marker; development gates, freeze, image, Azure activation, and live throughput remain open. v3.196 stays deployed with v3.195 rollback. No files moved.


Accepted v3.196 is frozen at `17f9bf4638371e0a21910fada6e8b195cfb0558f`, published at immutable digest `sha256:49f1d1c32124c4af672b1f8a2300c0435a43bb68672aff66d2d28193390c3588`, and passed governed Azure deployment run `36099965934` with accepted v3.195 retained as rollback. Validation PR #538 passed exact-head candidate gates and closed without merge; all 44 development and 45 frozen checks passed. The bounded scheduled worker, isolated Microsoft 365 intake, live identity/sign-in, and cleanup gates passed. This does not complete issue #520's 10,000-file nested drain, ZIP/member/customer routing, or recovery acceptance. Wix all-page desktop/mobile UX and Advisor DOCX-to-SharePoint acceptance remain open.

Accepted v3.195 is frozen at `9c88ae561d498b53d126863fe1c9ced52f8c276b`, published at immutable digest `sha256:035ef8684d2092fc6eb1f2b51769c6e7e30b443b2e28dd571e6edecf54b32ecd`, and passed governed Azure deployment run `36093814271` with v3.193 retained as rollback. The scheduled worker observed 20 discovered files, five promotions, 34 retry-required records, three oversized holds, and zero exception reviews. This accepted bounded pass does not complete issue #520's fair 10,000-file nested drain, ZIP/member routing, or recovery acceptance. The empty `20 Salus Enterprise Knowledge` folder inside `10 Pending Classification` has item ID `01DBTAFUOMR2BU2SRKGBAY3INJKHT6TB74`; it is not enabled as a bulk route and holds no source files. Frozen v3.194 was superseded before publication because its runtime marker was 3.193. Exact frozen branches and workflow results remain authoritative.

Frozen `release/v3.194` at `8667fbe7776b7109338d638abf152f40d95f2a7c` passed source CI but declares runtime version 3.193. Its immutable image publication was not attempted because the protected workflow requires the runtime identity to equal the release branch. Validation PR #537 passed all candidate workflows and closed without merge; exact head `9c88ae561d498b53d126863fe1c9ced52f8c276b` advanced non-force to development with runtime identity 3.195. Accepted v3.193 remains live, v3.192 is its rollback, and the corrected successor awaits development/frozen gates and separate release-specific authorization before image publication. The v3.194 oversize-ledger source change is retained in the successor. Issue #520 still requires enterprise-only routing and live 10,000-file acceptance.

Frozen v3.180 passed live Microsoft 365 acceptance. The operational diagnostic then counted 549 pending items. Candidate v3.181 processes at most 20 pending items per pass, verifies each item's current parent and ETag before reading, and defers archived extraction retries until the pending backlog is cleared. Accepted v3.180 remains active until the new release passes live acceptance.

Frozen v3.179 passed CI and image publication, but live Microsoft 365 acceptance saw a repeated Graph item during a concurrent folder move. The governed workflow restored accepted v3.178. Candidate v3.180 keeps the bounded continuation traversal and deduplicates valid item IDs; regression checks cover repeated entries, cross-origin links, cycles, and malformed IDs.

Release v3.178 is deployed with v3.176 retained as rollback. A new batch exceeded the single Microsoft Graph folder page and stopped intake before discovery. Candidate v3.179 traverses same-folder continuation pages with a 2,000-item bound and rejects cross-origin or cyclic links. Local pagination tests passed; live verification follows governed validation and deployment.

v3177_superseded_before_publication: Release v3.177 was frozen but its image publication was cancelled before deployment when an identical-content provenance constraint was found. Candidate v3.178 removes that constraint and has a duplicate regression check.\n\nRelease v3.176 at exact commit `12a13fdcb15e62276041553b83dee9699eddf7f4` is the accepted Azure development runtime, with v3.175 retained as rollback. The production image is pinned at `sha256:a420f6a14fb7b296d6cd565483da615f846b94014247a4b43915cfbf5959f430`. CI run `35863059484`, image publication run `35863701593`, and governed deployment run `35864255511` passed. Both pending originals were archived after exact destination verification; the DOCX canonical original matched its archived OneDrive source SHA-256.

## Source precedence

GitHub branches, commits, frozen releases, pull requests, workflow results, issues, and closed acceptance records. Those records control whenever they disagree with this file.

A missing, split, duplicated, or partially displayed conversation is not a build blocker and must not cause completed work to be recreated.

## Continuity procedure

Compare this record with the exact development head, controlled validation pull request, frozen release, activation records, and relevant Actions results.

Preserve the distinction among current development, frozen release, published immutable image, deployed runtime, accepted stable release, and rollback baseline.

After every required gate is green, close the controlled validation pull request without merge, then advance only the exact verified head through a non-force fast-forward.

A failed or inconsistent gate fails closed. Never weaken a security, privacy, accessibility, abuse, recovery, rollback, identity, tenant, disclosure, provenance, or human-authority control to make a release pass.

## Standing controls

Human-First Communications and Human Trust & Comprehension doctrine remain in force.

Never place credentials, confidential Protected Member information, personal information, investigation content, secrets, or unnecessary financial data in this file.

Keep Microsoft Graph access least-privilege, exact-folder scoped, auditable, revocable, and separately governed from report publication or other write paths.
