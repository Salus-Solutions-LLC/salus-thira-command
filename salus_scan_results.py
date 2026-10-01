"""Fail-closed comparison of a Defender result with one pending upload.

The caller must first authenticate the Event Grid delivery and load the
tenant-bound pending manifest from trusted storage. A matching event alone
never authorizes access: re-read the blob version, eTag and bytes before copy.
"""

import re


_SHA256 = re.compile(r"[0-9a-fA-F]{64}\Z")


def defender_result_for_pending(event, *, topic, blob_uri, etag, sha256):
    """Return `Clean` only for an exact, unambiguous no-threat result."""
    if not isinstance(event, dict) or not isinstance(event.get('data'), dict):
        return 'Unscanned'
    data = event['data']
    details = data.get('scanResultDetails')
    if not isinstance(details, dict):
        return 'Unscanned'
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        return 'Unscanned'
    if not all(isinstance(value, str) and value for value in (topic, blob_uri, etag)):
        return 'Unscanned'
    if (event.get('eventType') != 'Microsoft.Security.MalwareScanningResult'
            or event.get('topic') != topic
            or data.get('blobUri') != blob_uri
            or data.get('eTag') != etag
            or not isinstance(details.get('sha256'), str)
            or not _SHA256.fullmatch(details['sha256'])
            or details['sha256'].lower() != sha256.lower()):
        return 'Unscanned'
    if data.get('scanResultType') == 'Malicious':
        return 'Malicious'
    if data.get('scanResultType') != 'No threats found':
        return 'Unscanned'
    malware_names = details.get('malwareNamesFound', [])
    if not isinstance(malware_names, list) or malware_names:
        return 'Unscanned'
    return 'Clean'
