# Knowledge representation-gap reconciliation

Status: governed candidate; no live execution or recovery acceptance yet.

## Scope and authority

This implements Marc's request to reconcile the measured 116-file representation gap, establish a stable census, verify receipts/cleanup and record the next recovery steps. SAL-D116/SAL-D117 and SALUS-SEARCH-001 control source coverage; SAL-D118/SAL-D119 extraction review and retry pauses remain intact. Exact-head checks, Marc's approval and the protected environment precede execution.

The intervention cap is **116 currently missing source IDs**, not an assumption that today's gap remains exactly 116. A larger live gap stops the operation. A zero gap produces an auditable zero-item batch and proceeds to current census verification. No existing row is overwritten, restored from Removed, deleted, reassigned, released or made processing-eligible.

## Inventory and parked metadata

Enumerate the complete configured SalCAPA Intake root with read-only Graph delta metadata. Require the exact seven governed top-level areas, correct drive/ancestry, terminating scoped pagination, no shortcuts and complete source version/size provenance. Two complete pre-enrollment inventories must match, including source versions, parentage, names and metadata. The source corpus must remain at least the accepted minimum.

For each source absent from the existing candidate/hold/nonremoved-file union, add a provenance-bound metadata-only file row in the existing bulk inventory. Its scope key (legacy column name `pending_id`) is the **verified intake root ID**, distinct from the scheduled `10 Pending Classification` scope. Preserve the actual source-area ID/name, actual parent ID, relative path, ETag, modified time, size, trusted URL and source-stored attribution. Set `representation_only=true`, `processing_authorized=false`, status `Assignment Required` and fixed review reason.

This root inventory scope is essential. An ordinary Pending delta update can reset an Assignment Required row in its own scope; using that scope for the parked inventory could re-enable it. The root-scoped row is outside that cursor, and the normal scheduler also excludes its status. Normal authorized intake may continue independently in its original scope. The reconciliation does not pause, accelerate, reconfigure or invoke that pipeline. It does not infer completed extraction, source truth, rights clearance, a Protected Member assignment or permission from the new metadata.

## Atomicity and durable evidence

Create two restricted audit tables:

- `m365_knowledge_representation_batches`: unique operation key and batch ID, source drive/root, canonical manifest SHA-256, item count, actor and UTC timestamp.
- `m365_knowledge_representation_events`: one immutable-intent metadata event per included source, keyed to the operation and carrying the exact source metadata/version and fixed event type.

Within one transaction, acquire short database write exclusion (PostgreSQL lock timeout three seconds), recheck the exact missing membership, insert only absent parked rows with conflict-fail behavior, add every event and the batch record, and require zero missing source IDs. Roll back the entire batch on any conflict or failure. Existing/Removed root-scope collisions require review; they are never overwritten. The schema may remain created but empty after a rolled-back batch.

Open a fresh database connection and verify every parked field, event payload, manifest hash, drive/root, count, actor and timestamp. Log only aggregate counts, audit IDs, hashes, closed-set states and exception type/stage. Source names, identifiers, paths, ownership, URLs, content and raw exceptions remain in restricted records.

A valid committed metadata batch is retained even if later source drift blocks global census acceptance. Preserve its ID and reconcile durable evidence; do not delete it, blindly repeat an activation or infer global success. The unique operation key prevents a second commit.

## Stable census and task search

Before any new search, durably confirm that the prior PR #1225 census actor and this operation have no existing task receipts. Existing receipts stop execution for reconciliation.

Run four task-specific full represented-boundary queries. Both full search censuses must exactly match the pre-enrollment source inventory; source membership must be fully represented. Check each new receipt's exact query hash, actor, time and coverage fields from committed database storage. Require represented=considered, match/no-match and availability reconciliation, stable ledger membership and stable recovery metadata. Report the service's existing broad Complete-based count separately from exact extraction-status/nonempty-text counts. Neither definition alone qualifies content for customer use.

The logging order emits safe failure/stage/counter markers **before** success assertions, addressing the prior run's hidden failure-marker limitation. A partial receipt, a committed enrollment batch or completed metadata listing is not a completed task search.

## Execution and cleanup

Use the existing pinned v3.273 diagnostic image, managed identity and protected diagnostic concurrency; accepted application/worker remain v3.223. The isolated job has 900 seconds and zero replica retries. This is not a new application release or permission change.

Compare all selected application and worker identity/configuration/template fields using the identical pinned ARM API `2025-07-01`; suppress no differences. Always remove only the exact task-tagged/image-bound isolated job and verify absence, independently of census success.

After the run, update CURRENT_HANDOFF.md with exact source/merge/run, actual gap and enrollment counts, durable batch/events and four receipts or explicit partial/zero evidence, current recovery groups, unchanged runtime, cleanup, limitations, owner and next action.

## Acceptance and next recovery boundary

Acceptance requires every above gate, zero missing current sources, stable complete inventories, verified enrollment/audit readback, all four durable receipts, stable recovery-category reconciliation, unchanged runtime and isolated-job absence. No source contents are downloaded. Metadata representation is not recovery of the previously unresolved contents.

Use measured current recovery categories to prepare separately validated processor-specific recovery batches. Existing holds, paused retries, source restrictions, qualification and customer release remain governed. Never reuse the historical 7,923 as an immutable live total or hide new source additions.
