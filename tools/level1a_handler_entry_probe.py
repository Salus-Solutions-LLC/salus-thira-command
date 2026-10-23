"""One-use, read-only boundary check for the held fictional Level 1A scan.

The exact trusted queue event is passed through the production handlers with a
sentinel quarantine reader. The sentinel stops before any document bytes are
read, clean copy is written, or database status is changed. Output is fixed
booleans/counts only; no event, path, name, or document data is logged.
"""

import base64
import binascii
import json
import os
import re

from azure.identity import ManagedIdentityCredential
from azure.storage.queue import QueueClient

from salus_scan_results import (defender_event_matches_pending,
                                defender_result_for_pending, same_blob_etag)
from salus_scan_worker import process_queue_message


class StopBeforeRead(Exception):
    pass


class SentinelQuarantine:
    def read_version(self, _manifest):
        raise StopBeforeRead()


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


def main():
    if any(os.getenv(key) != value for key, value in {
            'SALUS_ENV': 'dev', 'SALUS_DB_BACKEND': 'postgres',
            'SALUS_PACKAGE_SCAN_MODE': 'defender'}.items()):
        raise SystemExit('handler_entry_guard_failed')
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '').strip()
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '').strip()
    identity = os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '').strip()
    if not (re.fullmatch(r'https://[a-z0-9]{3,24}\.queue\.core\.windows\.net/scan-results', queue_url)
            and topic.startswith('/subscriptions/') and identity):
        raise SystemExit('handler_entry_config_failed')

    from app import (db, process_level1a_scan_result,
                     process_package_scan_result)
    conn = db()
    try:
        rows = [dict(row) for row in conn.execute(
            'SELECT * FROM level1a_pending_scans WHERE order_id=?', (10,)).fetchall()]
        if len(rows) != 1 or rows[0]['status'] != 'Pending' or rows[0]['scan_event_id']:
            print(json.dumps({'handler_entry_probe': 'state_changed',
                              'order_row_count': len(rows)}))
            return
        row = rows[0]
        matches = [candidate for candidate in conn.execute(
            'SELECT etag FROM level1a_pending_scans WHERE blob_uri=?',
            (row['blob_uri'],)).fetchall()
            if same_blob_etag(candidate['etag'], row['etag'])]
        legacy_count = conn.execute(
            'SELECT COUNT(*) AS n FROM package_intake_pending_scans WHERE blob_uri=?',
            (row['blob_uri'],)).fetchone()['n']
    finally:
        conn.close()
    if len(matches) != 1 or legacy_count != 0:
        print(json.dumps({'handler_entry_probe': 'scope_mismatch',
                          'level1a_match_count': len(matches),
                          'legacy_uri_count': legacy_count}))
        return

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
                exact.append((message.content, event))
    if len(exact) != 1:
        print(json.dumps({'handler_entry_probe': 'inconclusive',
                          'exact_event_count': len(exact)}))
        return
    content, event = exact[0]
    if (not isinstance(event.get('id'), str) or not event['id']
            or not defender_event_matches_pending(
                event, topic=topic, blob_uri=row['blob_uri'],
                etag=row['etag'], sha256=row['content_sha256'])
            or defender_result_for_pending(
                event, topic=topic, blob_uri=row['blob_uri'],
                etag=row['etag'], sha256=row['content_sha256']) != 'Clean'):
        print(json.dumps({'handler_entry_probe': 'event_mismatch'}))
        return
    envelope_accepted = process_queue_message(
        content, process_event=lambda candidate:
        'Promoted' if isinstance(candidate, dict)
        and candidate.get('id') == event['id'] else 'Unmatched')

    # A matching legacy row could otherwise cause a status write. The strict
    # zero-collision guard above prevents that path in this read-only check.
    sentinel = SentinelQuarantine()
    try:
        legacy_outcome = process_package_scan_result(
            event, quarantine=sentinel, expected_topic=topic)
    except StopBeforeRead:
        print(json.dumps({'handler_entry_probe': 'legacy_scope_changed'}))
        return
    if legacy_outcome != 'Unmatched':
        print(json.dumps({'handler_entry_probe': 'legacy_scope_changed'}))
        return
    try:
        level1a_outcome = process_level1a_scan_result(
            event, quarantine=sentinel, expected_topic=topic)
    except StopBeforeRead:
        level1a_outcome = 'ReachedRead'
    if level1a_outcome not in ('ReachedRead', 'Unmatched', 'Reconcile'):
        raise SystemExit('handler_entry_unexpected_outcome')
    print(json.dumps({'handler_entry_probe': 'read_only',
                      'queue_envelope_accepted': envelope_accepted,
                      'legacy_unmatched': True,
                      'level1a_outcome': level1a_outcome}, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # No exception message can leave the protected job.
        print(json.dumps({'handler_entry_probe': 'failed',
                          'failure_class': type(exc).__name__}))
        raise SystemExit(1)
