# SalCAPA v3.37 Release Notes

## Governed universal material records and cross-component provenance

SalCAPA now persists generic, tenant-scoped material/source records independently
from any single assessment, evidence item, observation, intelligence finding,
operation, task, or report. One preserved original can be referenced by multiple
authorized SalCAPA processes without silently duplicating the source or losing
its provenance.

Each material record retains its server-assigned tenant, immutable record key,
original filename, controlled storage key, content type, byte size, SHA-256
digest, submitted source/origin context, acquisition and ingestion times,
uploader identity, sensitivity, purpose tags, description, optional
recording/possession authority basis, processing state, security-scan result,
retention, legal hold, disposition, disclosure status, and original/derived or
duplicate lineage fields.

Uploads are size-limited, filename-normalized, security-scanned, content-hashed,
and written through the governed local or Azure Blob storage provider. Identical
bytes within a tenant reuse the existing stored object while retaining a
distinct source receipt and explicit duplicate relationship. Downloads
recompute the content hash and fail closed on integrity mismatch.

## Human authority, disclosure, and lifecycle controls

Material processing follows explicit workflow states: Received, Security Review,
Quarantined, Ready for Processing, Processing, Ready for Human Review, Linked /
Promoted, and Rejected. These are workflow states and do not use the
danger-to-safe readiness continuum.

Tenant, uploader, ingestion time, content hash, processing state, provenance,
disclosure, legal hold, and link authority are server-controlled. Protected
Member users cannot promote, link, reclassify, disclose, or dispose material.
Salus personnel with decision authority must document processing, disclosure,
governance, and cross-component link actions. A material item cannot be linked
until it reaches human review, and linking never converts it into verified
evidence, qualified intelligence, a SalTHIRA finding, an executive decision, or
operational authority.

Salus-internal material remains hidden from Protected Member users until an
authorized Salus disclosure decision approves it for that tenant. Protected
Member submissions remain role-aware: the submitter and the tenant's Client
Executive can access them, subject to sensitivity clearance. Cross-tenant access
fails closed and is recorded as a security event.

## Recovery and runtime parity

Generic materials, governed links, and complete event history are included in
portable tenant backup/restore, validation, PostgreSQL sequence handling, and
SQLite-to-PostgreSQL migration. Stored objects are packaged once by storage key,
including intentionally deduplicated source receipts. Clean-room restore breaks
self-referential lineage safely before replacement and reconstructs the governed
graph in dependency order.

The exact v3.37 runtime, persistence, migration, and acceptance files are
preserved in a digest-verified deterministic source snapshot. Acceptance runs
the material lifecycle on SQLite, PostgreSQL 16, and both database modes in the
production container, alongside dependency audit, Bandit, repository hygiene,
Azure policy/infrastructure validation, and CodeQL.

Personnel Assessment and Facility Assessment remain on hold and are neither
implemented nor exposed by this release.
