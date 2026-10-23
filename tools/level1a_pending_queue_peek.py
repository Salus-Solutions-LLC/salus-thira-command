"""One-use, read-only comparison of the held queue with fictional paid order 10.

Runs under the existing private scan worker identity. Never receives, deletes,
acknowledges or changes a queue message, Blob, database row or job definition.
Only fixed-category counts leave the protected execution.
"""

import base64
import binascii
import collections
import json
import os

from salus_scan_results import (defender_event_matches_pending,
                                defender_result_for_pending, same_blob_etag)


def decode_events(content):
    if not isinstance(content, str) or len(content) > 65536:
        return None
    try:
        events = json.loads(content)
    except (TypeError, ValueError):
        try:
            decoded = base64.b64decode(content, validate=True)
            if not decoded or len(decoded) > 65536:
                return None
            events = json.loads(decoded.decode('utf-8'))
        except (binascii.Error, UnicodeError, ValueError):
            return None
    if isinstance(events, dict):
        events = [events]
    return events if isinstance(events, list) and 1 <= len(events) <= 10 else None


def classify(messages, row, topic):
    counts = collections.Counter()
    for message in messages:
        events = decode_events(message.content)
        if events is None:
            counts['invalid_message'] += 1
            continue
        for event in events:
            if not isinstance(event, dict) or not isinstance(event.get('data'), dict):
                counts['invalid_event'] += 1
                continue
            data = event['data']
            if data.get('blobUri') != row['blob_uri']:
                counts['other_uri'] += 1
                continue
            counts['same_uri'] += 1
            if event.get('eventType') != 'Microsoft.Security.MalwareScanningResult':
                counts['type_mismatch'] += 1
            if event.get('topic') != topic:
                counts['topic_mismatch'] += 1
            if not same_blob_etag(row['etag'], data.get('eTag')):
                counts['etag_mismatch'] += 1
            details = data.get('scanResultDetails')
            digest = details.get('sha256') if isinstance(details, dict) else None
            if isinstance(digest, str) and digest and digest.lower() != row['content_sha256'].lower():
                counts['digest_mismatch'] += 1
            if defender_event_matches_pending(
                    event, topic=topic, blob_uri=row['blob_uri'],
                    etag=row['etag'], sha256=row['content_sha256']):
                counts['qualified_match'] += 1
                result = defender_result_for_pending(
                    event, topic=topic, blob_uri=row['blob_uri'],
                    etag=row['etag'], sha256=row['content_sha256'])
                counts['result_' + result if result in ('Clean', 'Malicious', 'Unscanned')
                       else 'result_other'] += 1
    allowed = ('invalid_message', 'invalid_event', 'other_uri', 'same_uri',
               'type_mismatch', 'topic_mismatch', 'etag_mismatch',
               'digest_mismatch', 'qualified_match', 'result_Clean',
               'result_Malicious', 'result_Unscanned', 'result_other')
    return {key: counts[key] for key in allowed}


def main():
    if any(os.getenv(key) != value for key, value in {
            'SALUS_ENV': 'dev', 'SALUS_DB_BACKEND': 'postgres',
            'SALUS_PACKAGE_SCAN_MODE': 'defender'}.items()):
        raise SystemExit('pending_queue_probe_guard_failed')
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '')
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '')
    identity = os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '')
    if not (queue_url.startswith('https://') and queue_url.endswith('/scan-results')
            and topic.startswith('/subscriptions/') and identity):
        raise SystemExit('pending_queue_probe_config_failed')
    from app import db
    conn = db()
    try:
        rows = [dict(row) for row in conn.execute(
            'SELECT blob_uri,etag,content_sha256,status,scan_event_id '
            'FROM level1a_pending_scans WHERE order_id=?', (10,)).fetchall()]
    finally:
        conn.close()
    if len(rows) != 1 or rows[0]['status'] != 'Pending':
        print(json.dumps({'pending_queue_probe': 'inconclusive',
                          'pending_row_count': len(rows)}))
        return
    from azure.identity import ManagedIdentityCredential
    from azure.storage.queue import QueueClient
    client = QueueClient.from_queue_url(
        queue_url, credential=ManagedIdentityCredential(client_id=identity))
    messages = list(client.peek_messages(max_messages=16))
    output = {'pending_queue_probe': 'read_only',
              'pending_row_count': 1,
              'has_recorded_event': bool(rows[0]['scan_event_id']),
              'visible_message_count': len(messages),
              'categories': classify(messages, rows[0], topic)}
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Exception text may contain a member URI, account, token or path.
        print(json.dumps({'pending_queue_probe': 'failed',
                          'failure_class': type(exc).__name__}))
        raise SystemExit(1)
