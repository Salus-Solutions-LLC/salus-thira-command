import json

from salus_scan_worker import process_queue_message, poll_once


class Message:
    id = 'message-1'
    pop_receipt = 'receipt-1'

    def __init__(self, content):
        self.content = content


class Queue:
    def __init__(self, content):
        self.message = Message(content)
        self.deleted = []

    def receive_messages(self, **kwargs):
        assert kwargs == {'messages_per_page': 1, 'visibility_timeout': 120}
        return iter([self.message])

    def delete_message(self, message_id, receipt):
        self.deleted.append((message_id, receipt))


def test_queue_ack_requires_durable_result(monkeypatch):
    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    queue = Queue(json.dumps([{'id': 'event-1'}]))
    assert poll_once(queue_client=queue, process_event=lambda event: 'Promoted') == 'Acknowledged'
    assert queue.deleted == [('message-1', 'receipt-1')]
    queue = Queue(json.dumps([{'id': 'event-1'}]))
    assert poll_once(queue_client=queue, process_event=lambda event: 'Unmatched') == 'Held'
    assert not queue.deleted


def test_queue_never_acks_malformed_or_partial_message():
    assert not process_queue_message('{broken', process_event=lambda event: 'Promoted')
    assert not process_queue_message('[]', process_event=lambda event: 'Promoted')
    assert not process_queue_message(json.dumps([{'id': 1}, {'id': 2}]),
        process_event=lambda event: 'Promoted' if event['id'] == 1 else 'Reconcile')
