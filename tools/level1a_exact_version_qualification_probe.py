"""One-use read-only exact-version qualification of fictional paid order 10.

The existing worker identity reads the quarantined named version into process
memory solely to compare its recorded size/hash and approved Clean event.
No bytes, identifiers, paths, hashes, event payloads or exception text leave
the protected execution. It never writes or acknowledges anything.
"""

import base64
import binascii
import json
import os
import re

from azure.identity import ManagedIdentityCredential
from azure.storage.queue import QueueClient

from app import db, package_quarantine
from salus_scan_results import (defender_event_matches_pending,
                                defender_result_for_pending,
                                qualified_clean_quarantine_object,
                                same_blob_etag)


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


def safe_class(exc):
    kind = type(exc).__name__
    return kind if re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,63}', kind) else 'Other'


def main():
    if any(os.getenv(key) != value for key, value in {
            'SALUS_ENV': 'dev', 'SALUS_DB_BACKEND': 'postgres',
            'SALUS_PACKAGE_SCAN_MODE': 'defender'}.items()):
        raise SystemExit('exact_version_probe_guard_failed')
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '')
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '')
    identity = os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '')
    if not (queue_url.startswith('https://') and queue_url.endswith('/scan-results')
            and topic.startswith('/subscriptions/') and identity):
        raise SystemExit('exact_version_probe_config_failed')
    conn = db()
    try:
        rows = [dict(row) for row in conn.execute(
            'SELECT * FROM level1a_pending_scans WHERE order_id=?', (10,)).fetchall()]
    finally:
        conn.close()
    if len(rows) != 1 or rows[0]['status'] != 'Pending':
        print(json.dumps({'exact_version_probe': 'inconclusive',
                          'pending_row_count': len(rows)}))
        return
    row = rows[0]
    queue = QueueClient.from_queue_url(
        queue_url, credential=ManagedIdentityCredential(client_id=identity))
    exact = []
    for message in queue.peek_messages(max_messages=16):
        events = decode_events(message.content)
        if not events:
            continue
        for event in events:
            if (isinstance(event, dict) and isinstance(event.get('data'), dict)
                    and event['data'].get('blobUri') == row['blob_uri']
                    and same_blob_etag(row['etag'], event['data'].get('eTag'))):
                exact.append(event)
    if len(exact) != 1:
        print(json.dumps({'exact_version_probe': 'inconclusive',
                          'exact_event_count': len(exact)}))
        return
    event = exact[0]
    if not defender_event_matches_pending(
            event, topic=topic, blob_uri=row['blob_uri'],
            etag=row['etag'], sha256=row['content_sha256']):
        print(json.dumps({'exact_version_probe': 'event_mismatch'}))
        return
    result = defender_result_for_pending(
        event, topic=topic, blob_uri=row['blob_uri'],
        etag=row['etag'], sha256=row['content_sha256'])
    if result != 'Clean':
        print(json.dumps({'exact_version_probe': 'non_clean'}))
        return
    pending = dict(row, sha256=row['content_sha256'])
    try:
        snapshot = package_quarantine(for_worker=True).read_version(pending)
    except Exception as exc:
        print(json.dumps({'exact_version_probe': 'version_read_failed',
                          'failure_class': safe_class(exc)}))
        return
    qualifies = qualified_clean_quarantine_object(
        event, pending, snapshot, topic=topic,
        tenant_id=row['tenant_id'], assessment_id=row['assessment_id'],
        intake_request_id=row['intake_request_id'])
    print(json.dumps({'exact_version_probe': 'read_only',
                      'named_version_read': True,
                      'qualified_clean': bool(qualifies)}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'exact_version_probe': 'failed',
                          'failure_class': safe_class(exc)}))
        raise SystemExit(1)
