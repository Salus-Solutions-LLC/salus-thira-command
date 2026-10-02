"""Dedicated, managed-identity consumer for Defender small-upload results.

Run separately from the web process. Never expose this as an HTTP endpoint.
Unknown and failed results stay on the queue for a governed reconciliation path.
"""

import json
import os
import re
from itertools import islice


_QUEUE_URL = re.compile(r'https://[a-z0-9]{3,24}\.queue\.core\.windows\.net/scan-results\Z')


def process_queue_message(content, *, process_event):
    """Return True only when every trusted-queue event was durably handled."""
    if not isinstance(content, str) or len(content) > 65536:
        return False
    try:
        events = json.loads(content)
    except (TypeError, ValueError):
        return False
    if isinstance(events, dict):
        events = [events]
    if not isinstance(events, list) or not events or len(events) > 10:
        return False
    for event in events:
        if not isinstance(event, dict):
            return False
        outcome = process_event(event)
        if outcome not in ('Promoted', 'Malicious', 'Unscanned'):
            return False
    return True


def poll_once(*, queue_client=None, process_event=None):
    """Check a bounded group; one held message must not starve later results."""
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '').strip()
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '').strip()
    if not _QUEUE_URL.fullmatch(queue_url) or not topic.startswith('/subscriptions/'):
        raise RuntimeError('The governed scan-result queue and topic are not configured.')
    if queue_client is None:
        from azure.identity import ManagedIdentityCredential
        from azure.storage.queue import QueueClient
        client_id = os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '').strip()
        if not client_id:
            raise RuntimeError('The governed scan worker identity is not configured.')
        credential = ManagedIdentityCredential(client_id=client_id)
        queue_client = QueueClient.from_queue_url(queue_url, credential=credential)
    if process_event is None:
        from app import process_package_scan_result
        process_event = lambda event: process_package_scan_result(event, expected_topic=topic)
    messages = queue_client.receive_messages(messages_per_page=5, max_messages=5,
                                             visibility_timeout=120)
    held = acknowledged = False
    for message in islice(messages, 5):
        if not process_queue_message(message.content, process_event=process_event):
            held = True
            continue
        queue_client.delete_message(message.id, message.pop_receipt)
        acknowledged = True
    return 'Held' if held else 'Acknowledged' if acknowledged else 'Empty'


def main(*, poll=None, reconcile=None):
    # Azure and processing exceptions can include a Blob URL or Member path.
    # Report only the failure class in routine job output; keep the item held.
    try:
        result = (poll or poll_once)()
        if result not in ('Acknowledged', 'Empty', 'Held'):
            raise RuntimeError('Unknown scan-result worker outcome.')
        if reconcile is None:
            from app import reconcile_stale_package_scans
            reconcile = reconcile_stale_package_scans
        reconcile()
    except Exception as exc:
        print(json.dumps({'scan_result_job': 'failed',
                          'error_type': type(exc).__name__}, sort_keys=True))
        return 1
    return 2 if result == 'Held' else 0


if __name__ == '__main__':
    raise SystemExit(main())
