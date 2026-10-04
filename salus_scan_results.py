"""Fail-closed comparison of a Defender result with one pending upload.

The caller must first authenticate the Event Grid delivery and load the
tenant-bound pending manifest from trusted storage. A matching event alone
never authorizes access: re-read the blob version, eTag and bytes before copy.
"""

import hashlib
import re


_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")
_AZURE_ETAG = re.compile(r"0x[0-9a-fA-F]+\Z")


def same_blob_etag(recorded, observed):
    """Match only the same Azure ETag with or without one HTTP quote pair."""
    def canonical(value):
        if not isinstance(value, str):
            return None
        if len(value) > 2 and value[0] == value[-1] == '"':
            value = value[1:-1]
        return value if _AZURE_ETAG.fullmatch(value) else None

    expected = canonical(recorded)
    return expected is not None and expected == canonical(observed)


def defender_event_matches_pending(event, *, topic, blob_uri, etag, sha256):
    """Require the authenticated event to describe one exact pending original."""
    if not isinstance(event, dict) or not isinstance(event.get('data'), dict):
        return False
    data = event['data']
    details = data.get('scanResultDetails')
    if not isinstance(details, dict):
        return False
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        return False
    if not all(isinstance(value, str) and value for value in (topic, blob_uri, etag)):
        return False
    if (event.get('eventType') != 'Microsoft.Security.MalwareScanningResult'
            or event.get('topic') != topic
            or data.get('blobUri') != blob_uri
            or not same_blob_etag(etag, data.get('eTag'))):
        return False
    event_digest = details.get('sha256')
    if event_digest is None or event_digest == '':
        # A Clean result without an event digest is still provisional here:
        # the named Blob version, raw ETag, size and byte hash must be verified
        # independently before the caller can promote any bytes.
        return data.get('scanResultType') == 'No threats found'
    return (isinstance(event_digest, str)
            and bool(_SHA256.fullmatch(event_digest))
            and event_digest.lower() == sha256.lower())


def defender_result_for_pending(event, *, topic, blob_uri, etag, sha256):
    """Return `Clean` only for an exact, unambiguous no-threat result."""
    if not defender_event_matches_pending(event, topic=topic, blob_uri=blob_uri,
                                          etag=etag, sha256=sha256):
        return 'Unscanned'
    data = event['data']
    details = data['scanResultDetails']
    if data.get('scanResultType') == 'Malicious':
        return 'Malicious'
    if data.get('scanResultType') != 'No threats found':
        return 'Unscanned'
    malware_names = details.get('malwareNamesFound', [])
    if not isinstance(malware_names, list) or malware_names:
        return 'Unscanned'
    return 'Clean'


def qualified_clean_quarantine_object(event, pending, snapshot, *, topic,
                                      tenant_id, assessment_id, intake_request_id):
    """Check one scoped, versioned original before any caller promotes its bytes.

    `pending` must come from the trusted tenant-bound intake ledger; `snapshot`
    must come from a managed-identity read of that blob's *named version*.
    The queue processor authenticates the queue, performs the read and then
    makes the status/copy transition under a database lock. This pure check
    does not grant access or change either store.
    """
    if not isinstance(pending, dict) or not isinstance(snapshot, dict):
        return False
    if pending.get('status') != 'Pending':
        return False
    for field, expected in (('tenant_id', tenant_id),
                            ('assessment_id', assessment_id),
                            ('intake_request_id', intake_request_id)):
        if not isinstance(expected, int) or expected < 1 or pending.get(field) != expected:
            return False
    uri = pending.get('blob_uri')
    version = pending.get('blob_version_id')
    etag = pending.get('etag')
    digest = pending.get('sha256')
    size = pending.get('size_bytes')
    data = snapshot.get('bytes')
    if (not all(isinstance(value, str) and value for value in (uri, version, etag))
            or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
            or not isinstance(size, int) or size < 1
            or not isinstance(data, bytes) or len(data) != size):
        return False
    if (snapshot.get('blob_uri') != uri
            or snapshot.get('blob_version_id') != version
            or snapshot.get('etag') != etag
            or hashlib.sha256(data).hexdigest() != digest.lower()):
        return False
    return defender_result_for_pending(event, topic=topic, blob_uri=uri,
                                       etag=etag, sha256=digest) == 'Clean'
