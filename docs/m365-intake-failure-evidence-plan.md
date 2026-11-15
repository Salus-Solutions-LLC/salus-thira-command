# Microsoft 365 intake failure evidence plan

Status: proposed diagnostic design, 15 November 2026. This document does not authorize a runtime change, deployment, protected workflow execution, reader activation or assessment.

## Evidence and limits

Consumed v3.276 deployment run 43679803060 rejected a listed document before downloading that failed item. The retained log identifies the consistency guard but omits its candidate and failed predicate. Current observations cannot reconstruct those missing historical facts.

On 15 November, the accepted v3.223 runtime completed metadata comparisons for all 33 items in its then-current pending listing. Every metadata request returned HTTP 200 and all six mismatch counters were zero. No file content was downloaded and no business record was written. This is a current-window result, not proof of historical source stability, document acceptance, a complete Library census or a working ChatGPT connection.

The attempted bounded archive probe stopped with ValueError. An independent no-client invocation verified that v3.223 rejects processed_only with max_files before any source request. Its live list_files method AST hash matches accepted source 5dff59b381a0c455f99c6f15d0e2a37c273f4056. Frozen v3.276 supports that bounded argument and streams listing pages differently. The read_listed_document method is identical between the releases, but the complete listing implementations are not interchangeable. Do not remove the bound or silently replace the live method to obtain an archive result. This compatibility limit does not explain the historical v3.276 failure, which occurred later at the document consistency guard.

## Proposed evidence contract

Prepare a source candidate that records the failed comparison while preserving the existing rejection, content-read order and acceptance/rollback gates. Evaluate the same six predicates against the same freshly returned metadata and saved listing used by the guard. Do not add a second metadata request to decide whether the first response should be accepted.

The restricted diagnostic receipt should contain:

- Exact frozen source, immutable image, workflow run/attempt and diagnostic version.
- Listing completion and item-observation times in UTC; subtree and explicit listing/sample limits.
- A run-scoped opaque candidate reference and fixed format group, permitting correlation within that execution without logging raw source identifiers. Keep the random correlation material and any source mapping within the existing restricted evidence boundary. Do not publish a stable cross-run source fingerprint.
- Six fixed Boolean mismatch fields: id, name, etag, size, parent_boundary and listed_snapshot. Preserve simultaneous mismatches rather than reporting only the first condition.
- HTTP status and a fixed failure-stage code when no metadata comparison is possible. A failed or incomplete probe must not emit a successful-completion receipt.
- Content-download and business-write boundaries, cleanup outcome and the distinction between a new observation and the unavailable historical failure.

General CI logs may contain fixed stage/reason codes and aggregate counts only. Do not log candidate mappings, names, item or drive IDs, URLs, paths, raw metadata, eTags, exact compared sizes, tokens, credentials, document content or Protected Member identity. Do not include raw exception text or provider responses. Restricted evidence must remain outside repository-backed source, use existing access/retention controls and fail explicitly if durable readback cannot be verified.

If evidence recording fails, the existing consistency rejection must still occur before file content is read. Recording failure must never permit the document, alter its status, suppress the failure, skip the candidate or convert a failed acceptance into success. Preserve existing ancestry, version, exact-byte and If-Match protections.

## Required validation before any promotion

Use fictional sources to prove unchanged stable behavior; each of the six predicates independently; simultaneous mismatches; missing or non-200 metadata; altered saved snapshots; moved/out-of-bound items; correlation isolation across runs; safe diagnostic failure; and incomplete executions. Assert that no content method is called for a rejected item and that sensitive fixture strings are absent from every log, receipt intended for general CI, and exception path.

Test the deployed-version compatibility check before any live archive request. A diagnostic written for a newer listing implementation must stop with a fixed compatibility code on the accepted older version. Do not broaden to an unbounded archive traversal as a fallback.

The candidate must retain the disabled reader and unchanged business-record state. Re-run relevant unit/security/continuity checks on its exact head. Any frozen successor, image publication, protected deployment, live acceptance or change to access requires its own established authorization and immutable-release/rollback controls. The consumed v3.276 activation must not be replayed.

## Completion standard

A new failure can be diagnosed only when a candidate-correlated receipt identifies its actual predicate and stage, source/version and timing, with verified restricted retention. It remains a new failure observation. The historical cause must stay unproven unless independently retained evidence establishes it. A no-mismatch run is a bounded current observation and does not resolve the historical evidence gap.

The reader remains disabled. The assessment and future public-source/reunification collection remain on hold.

## Source candidate prepared on 15 November 2026

The standalone candidate is `tools/m365_intake_metadata_diagnostic.py`, with fictional tests in `tests/test_m365_intake_metadata_diagnostic.py` and a pull-request-only validation workflow. It is separate from the server, worker and live acceptance implementation. No existing intake method is changed or replaced. It is not included in the already published v3.276 image and has not been executed against live source records.

The candidate pins the accepted v3.223 and frozen v3.276 intake module and listing-method hashes. Unknown code fails before source access; a bounded archive on v3.223 returns ARCHIVE_BOUND_UNSUPPORTED without listing it. Pending listing is limited to 500 items and comparisons to 50; archive comparison selects at most one positive-size representative per supported family, with one fallback metadata item if none qualifies. It checks the time budget between operations and uses an eight-second item-request timeout. The existing listing timeout still applies to requests already in flight; this is not an absolute 45-second execution guarantee.

The restricted receipt contains run-scoped keyed candidate references, observation times, HTTP status, all six mismatch flags, source/version pins and explicit failure stage. The random correlation key is not retained. General output is a fixed aggregate summary without candidate references. A mismatch, incompatible version, empty listing, metadata error, elapsed budget or incomplete run produces failure. Client cleanup errors also produce a fixed failure summary.

A caller must supply an existing, authorized restricted receipt directory outside every Git working tree. The exclusive file sink prevents overwriting an existing receipt, flushes the file and verifies exact readback before a successful summary. The tool does not grant directory access or verify inherited Windows ACLs; the operator must establish the destination's existing handling boundary. Image identity is an operator pin and still requires independent Azure verification; the tool verifies local source hashes, not the registry/runtime image identity itself. A completed comparison receipt does not constitute deployment or content acceptance.

Fictional validation covers each predicate and simultaneous drift, raw-provider redaction, bounds, family selection, source pins, old-version compatibility, timeout/incompletion, changed or failed retention, run isolation, repository destination denial, CLI output and cleanup failure. The workflow has read-only repository permission, no Azure authentication, no protected environment, no push/dispatch trigger and no live-source execution.

Next: review the exact source candidate. Any live diagnostic must first reconcile the actual deployed source/image and an authorized restricted evidence destination, keep the reader disabled and retain the assessment hold. No new live execution is requested by this source review; no application promotion is prepared here.
