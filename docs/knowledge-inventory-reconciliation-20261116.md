# Governed read-only inventory reconciliation

Controlled candidate, 16 November 2026. Operation `salus-readonly-inventory-reconciliation-20261116`. Exact-version approval is required for the protected merge and isolated execution. This observation neither adopts a baseline nor authorizes proposal preparation, preflight, source-byte access, processing or retry/hold changes.

## Evidence and reconstruction boundary

Approved PR #1282 merged as `a6bde5bd842bb6618d0c975d06c4f5ef4147a823`. Run 43925327558 attempt 1 stopped before the writing transaction with `SOURCE_INVENTORY_CHANGED`. Its first two complete 23,747-file inventories matched digest `0e556598be30292cc1bbb2e46bb964b2e6e6f5e38f0b3b5e93b48a7cc68bc613`. Its final 23,748-file observation had digest `efd10c4ed8793e808d79076f57074afedc549d315985fe6f4dea98f1196e3621`. Commit attempted and acknowledged were both zero. The app/worker comparison and isolated-job absence passed; no new diagnostic/proposal/search receipts were saved. PR #1283 records this qualified outcome.

The immutable approved baseline retains each source's `current_source` inventory record. Page through all hash-bound baseline members, reconstruct the complete original inventory, and verify its count and digest against the approved header and failed run's first digest. Do not reconstruct identity from aggregate counts. The failed final snapshot's source values were not retained. Current values can reconstruct that snapshot only if their complete inventory digest matches its recorded digest; otherwise describe the differences strictly as current versus approved baseline and retain the historical gap.

## Read-only controls

Before enumeration, establish database-enforced REPEATABLE READ READ ONLY and independently reject DML, DDL, mutating CTEs, multiple statements, locking commands and transaction-mode changes through a strict SELECT facade. There is no write facade, receipt constructor, DDL or record-preparation path in the executable entry point. The same restrictions apply on a fresh independent connection after the final inventory observation. No planning-table locks or write transactions are taken.

Reverify the complete immutable baseline, parent plan, 200 remediation proposals and 200 prior reviews, all events and all twenty complete receipt rows against their saved private hashes and bindings. Inspect the failed operation's four target tables and both failed/current task receipt prefixes. Require empty targets; any saved output stops this candidate for separately governed reconciliation, without recreating or adopting it. Repeat this proof on the independent final connection. Other tasks' receipts are not counted as new receipts for this task.

## Stable inventory and source-level reconciliation

Use the pinned complete, content-free recursive inventory implementation, with all pages and existing boundary, identity, shortcut, ancestry and provenance checks. Permit at most three initial observations to obtain two consecutive complete inventories that are exactly equal. Take one final complete observation after the first database reconciliation; require it to equal the stable inventory in every row and metadata value. The total is at most four observations. Equal counts alone are insufficient. Any final drift fails without writes or baseline adoption.

Compare the reconstructed baseline and current inventory by exact source identity, reporting added, removed and changed rows plus overlapping version, size, parent/area, name/path, modified time, content tag, MIME, attribution, trusted URL and other-metadata differences. Compare all approved unresolved sources, the five separate availability exceptions and any other baseline protected hold/pause sources against their baseline critical identity/version/rights/availability bindings. Current-versus-baseline changes are findings, never authority to continue processing.

Reconcile each changed source to the approved unresolved set, availability exceptions, other baseline sources or outside-baseline identities, and to its current represented status. Bound the union of physical differences, protected-source critical changes and missing representation to 100 sources and 128 KiB of source-difference output. Refuse truncation or scope enlargement. Each emitted source record contains a SHA-256 identity binding, old/current row hashes, relation, difference type and fixed change-field categories. It contains no raw item ID, path, filename, owner, URL, extracted content or raw error. Hashes remain linkable restricted evidence, not a claim of anonymization; authorized follow-up can correlate them inside the governed source environment.

Run four task-specific read-only searches over every current represented identity, retaining considered/matched counts and the complete search-matrix digest. Physical identities not yet represented are separately considered by identity reconciliation. No new search receipt is created; metadata consideration does not establish content review or source qualification. Do not substitute physical-file counts for a represented-record census or enlarge the approved 8,430-source recovery scope.

## Independent verification and preservation

On the fresh final connection, recheck the full twenty-receipt and immutable input proof and the empty targets. Require the approved-source critical fingerprints to match the first read, preserving every version and rights binding. Compare all current paused-source and held-source memberships and the protected checkpoint attempts, due times, leases, status, reason and last-code fingerprints; any change fails. Review/observation clocks alone are excluded from approval and scheduling controls. Bounded changes to sources outside the approved/protected set are reported as observations, not adopted or processed. Current-versus-baseline pause/hold differences remain explicit findings even when stable during this read-only run.

Successful completion means the read-only evidence is internally consistent and the inventory is stable for the observed window. It does not mean all baseline differences are safe, complete, qualified or authorized for a later continuation. Historical membership, content, source-rights, archive-authenticity, chat-capture and independent global Compass/reader proof gaps remain open.

## Protected workflow and cleanup

The activation binds the approved input manifests, failed run and inventory digests, nine source hashes, six governing rows and five-module payload. The pre-Azure guard rejects changed fields, sources, rows, payloads and attempt replay. Only the governed branch push can activate it; no manual dispatch or rerun is supported. Keep v3.223 as the app/worker runtime and use the pinned v3.276 image solely for the isolated `salcapa-invrecon-b48224` job.

Retain 0.5 CPU, 1 GiB, 900 seconds, zero retries, the 786,432 KiB memory guard, 120-second read statement timeout, 262,144-byte decompressed payload limit and existing command-argument envelope. No source downloads or paid external API calls are authorized. The workflow validates complete terminal telemetry, all source-difference hashes, source limits and final stability evidence before claiming success.

Always compare full selected ARM identity/template/configuration for the app and worker. Delete only the task-tagged isolated job with its expected image, then independently list the namespace to prove absence. Inspect sanitized platform terminal/exit/OOM evidence before deletion. Cleanup does not establish successful reconciliation. Preserve Marc's personal SalusScan2 email opt-out, Compass pause and disabled reader.

## Result and next gates

Record exact implementation, merge, run/attempt, full receipt digest, empty-target proof, baseline/current inventory digests and differences, source bindings, approved-scope critical differences, physical/represented/unresolved counts, read-only query evidence, protected pause/hold/checkpoint proof, independent readback and cleanup. Preserve full prior handoff history. A mismatch or incomplete readback must remain a stop, with qualified evidence and no rerun.

After the measured results, prepare only the justified next governed candidate: representation repair for new identities, source-owner/rights resolution, a separately approved baseline proposal, or a bounded continuation that preserves the exact approved cohort. None is authorized by this reconciliation. Method adoption, exact source selection, preflight execution, byte reads and recovery processing retain separate gates.

## Primary guidance

- [Microsoft Graph driveItem delta](https://learn.microsoft.com/en-us/graph/api/driveitem-delta?view=graph-rest-1.0): complete hierarchy enumeration and paging; a current response does not reveal unretained historical source values.
- [PostgreSQL 16 transaction isolation](https://www.postgresql.org/docs/16/transaction-iso.html): snapshot semantics support internally consistent reads; independent observations require separate transactions/connections.

These specific design references are bounded research, not exhaustive internet or corpus-content qualification.
