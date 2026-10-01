"""Dedicated, managed-identity consumer for Defender small-upload results.

Run separately from the web process. Never expose this as an HTTP endpoint.
Unknown and failed results stay on the queue for a governed reconciliation path.
"""

import json
import os
import re


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
    """Receive one result; acknowledge only after a durable state transition."""
    queue_url = os.getenv('SALUS_SCAN_RESULTS_QUEUE_URL', '').strip()
    topic = os.getenv('SALUS_SCAN_RESULT_TOPIC_ID', '').strip()
    if not _QUEUE_URL.fullmatch(queue_url) or not topic.startswith('/subscriptions/'):
        raise RuntimeError('The governed scan-result queue and topic are not configured.')
    if queue_client is None:
        from azure.identity import ManagedIdentityCredential
        from azure.storage.queue import QueueClient
        credential = ManagedIdentityCredential(
            client_id=os.getenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', '').strip() or None)
        queue_client = QueueClient.from_queue_url(queue_url, credential=credential)
    if process_event is None:
        from app import process_package_scan_result
        process_event = lambda event: process_package_scan_result(event, expected_topic=topic)
    messages = queue_client.receive_messages(messages_per_page=1, visibility_timeout=120)
    for message in messages:
        if not process_queue_message(message.content, process_event=process_event):
            return 'Held'
        queue_client.delete_message(message.id, message.pop_receipt)
        return 'Acknowledged'
    return 'Empty'


if __name__ == '__main__':
    # A supervised job invokes bounded cycles and owns restart/telemetry.
    result = poll_once()
    from app import reconcile_stale_package_scans
    reconcile_stale_package_scans()
    if result == 'Held':
        raise SystemExit(2)
