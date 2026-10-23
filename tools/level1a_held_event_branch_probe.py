"""Read-only branch classification for one held fictional Level 1A event.

Uses one peek and scoped relational reads. Logs only fixed booleans and counts;
never reads Blob/document bytes or changes queue, database or Azure state.
"""

import base64
import binascii
import json
import os

from azure.identity import ManagedIdentityCredential
from azure.storage.queue import QueueClient

from app import db
from salus_scan_results import defender_event_matches_pending, same_blob_etag


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
        raise SystemExit('held_branch_guard_failed')
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '')
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '')
    identity = os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '')
    if not (queue_url.startswith('https://') and queue_url.endswith('/scan-results')
            and topic.startswith('/subscriptions/') and identity):
        raise SystemExit('held_branch_config_failed')
    conn = db()
    try:
        rows = [dict(row) for row in conn.execute(
            'SELECT id,tenant_id,buyer_user_id,order_id,assessment_id,'
            'intake_request_id,blob_uri,etag,content_sha256,status,scan_event_id '
            'FROM level1a_pending_scans WHERE order_id=?', (10,)).fetchall()]
        if len(rows) != 1 or rows[0]['status'] != 'Pending':
            print(json.dumps({'held_branch_probe': 'inconclusive',
                              'pending_row_count': len(rows)}))
            return
        row = rows[0]
        link_count = conn.execute(
            'SELECT COUNT(*) AS n FROM level1a_assessment_links WHERE '
            'tenant_id=? AND buyer_user_id=? AND order_id=? AND assessment_id=?',
            (row['tenant_id'], row['buyer_user_id'], row['order_id'],
             row['assessment_id'])).fetchone()['n']
        item_count = conn.execute(
            'SELECT COUNT(*) AS n FROM level1a_intake_items WHERE '
            'id=? AND tenant_id=? AND order_id=? AND assessment_id=?',
            (row['intake_request_id'], row['tenant_id'], row['order_id'],
             row['assessment_id'])).fetchone()['n']
        legacy_collision_count = conn.execute(
            'SELECT COUNT(*) AS n FROM package_intake_pending_scans WHERE blob_uri=?',
            (row['blob_uri'],)).fetchone()['n']
    finally:
        conn.close()
    if any(not isinstance(n, int) or n < 0 or n > 1
           for n in (link_count, item_count, legacy_collision_count)):
        raise SystemExit('held_branch_scope_ambiguous')
    client = QueueClient.from_queue_url(
        queue_url, credential=ManagedIdentityCredential(client_id=identity))
    messages = list(client.peek_messages(max_messages=16))
    exact = []
    for message in messages:
        events = decode_events(message.content)
        if not events:
            continue
        for event in events:
            if (isinstance(event, dict) and isinstance(event.get('data'), dict)
                    and event['data'].get('blobUri') == row['blob_uri']
                    and same_blob_etag(row['etag'], event['data'].get('eTag'))):
                exact.append(event)
    if len(exact) != 1:
        print(json.dumps({'held_branch_probe': 'inconclusive',
                          'exact_event_count': len(exact)}))
        return
    event = exact[0]
    output = {'held_branch_probe': 'read_only',
              'exact_event_count': 1,
              'event_id_present': isinstance(event.get('id'), str)
              and bool(event['id']),
              'paid_order_link_count': link_count,
              'intake_item_count': item_count,
              'legacy_uri_collision_count': legacy_collision_count,
              'event_qualifies_manifest': defender_event_matches_pending(
                  event, topic=topic, blob_uri=row['blob_uri'],
                  etag=row['etag'], sha256=row['content_sha256']),
              'already_recorded_event': bool(row['scan_event_id'])}
    print(json.dumps(output, sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'held_branch_probe': 'failed',
                          'failure_class': type(exc).__name__}))
        raise SystemExit(1)
