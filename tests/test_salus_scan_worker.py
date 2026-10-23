import base64
import json

from salus_scan_worker import main, process_queue_message, poll_once


class Message:
    id = 'message-1'
    pop_receipt = 'receipt-1'

    def __init__(self, content):
        self.content = content


class Queue:
    def __init__(self, content):
        self.messages = [Message(value) for value in
                         (content if isinstance(content, list) else [content])]
        for index, message in enumerate(self.messages, 1):
            message.id = f'message-{index}'
            message.pop_receipt = f'receipt-{index}'
        self.deleted = []

    def receive_messages(self, **kwargs):
        assert kwargs == {'messages_per_page': 5, 'max_messages': 5,
                          'visibility_timeout': 120}
        return iter(self.messages)

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


def test_held_message_does_not_starve_later_clean_result(monkeypatch):
    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    queue = Queue(['{broken', json.dumps({'id': 'clean'}),
                   json.dumps({'id': 'unmatched'})])
    assert poll_once(queue_client=queue,
                     process_event=lambda event: 'Promoted' if event['id'] == 'clean'
                     else 'Unmatched') == 'Held'
    assert queue.deleted == [('message-2', 'receipt-2')]


def test_queue_poll_is_bounded_to_five_messages(monkeypatch):
    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    queue = Queue([json.dumps({'id': str(index)}) for index in range(6)])
    assert poll_once(queue_client=queue, process_event=lambda event: 'Promoted') == 'Acknowledged'
    assert len(queue.deleted) == 5


def test_base64_event_grid_envelope_is_bounded_and_fail_closed(monkeypatch):
    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    wrapped = base64.b64encode(json.dumps({'id': 'fictional'}).encode()).decode()
    queue = Queue(wrapped)
    assert poll_once(queue_client=queue, process_event=lambda event: 'Promoted') == 'Acknowledged'
    assert queue.deleted == [('message-1', 'receipt-1')]
    assert not process_queue_message(wrapped, process_event=lambda event: 'Unmatched')
    assert not process_queue_message('%%%', process_event=lambda event: 'Promoted')
    assert not process_queue_message(base64.b64encode(b'not json').decode(),
                                     process_event=lambda event: 'Promoted')
    assert not process_queue_message(base64.b64encode(b'x' * 50000).decode(),
                                     process_event=lambda event: 'Promoted')


def test_queue_never_acks_malformed_or_partial_message():
    assert not process_queue_message('{broken', process_event=lambda event: 'Promoted')
    assert not process_queue_message('[]', process_event=lambda event: 'Promoted')
    assert not process_queue_message(json.dumps([{'id': 1}, {'id': 2}]),
        process_event=lambda event: 'Promoted' if event['id'] == 1 else 'Reconcile')


def test_queue_event_retries_only_transaction_deadlock_before_ack(monkeypatch):
    class DeadlockDetected(Exception):
        sqlstate = '40P01'

    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    queue = Queue(json.dumps({'id': 'event-1'}))
    calls = []
    def process_event(event):
        calls.append(event['id'])
        if len(calls) < 3:
            raise DeadlockDetected('private/member/path')
        return 'Promoted'

    monkeypatch.setattr('salus_scan_worker.time.sleep', lambda _: None)
    assert poll_once(queue_client=queue, process_event=process_event) == 'Acknowledged'
    assert calls == ['event-1'] * 3
    assert queue.deleted == [('message-1', 'receipt-1')]


def test_exhausted_queue_event_deadlock_keeps_message_unacknowledged(monkeypatch):
    class DeadlockDetected(Exception):
        sqlstate = '40P01'

    monkeypatch.setenv('SALUS_SCAN_RESULTS_QUEUE_URL',
                       'https://salusquarantine.queue.core.windows.net/scan-results')
    monkeypatch.setenv('SALUS_SCAN_RESULT_TOPIC_ID', '/subscriptions/test/topic')
    queue = Queue(json.dumps({'id': 'event-1'}))
    calls = []
    def process_event(event):
        calls.append(event['id'])
        raise DeadlockDetected('private/member/path')

    monkeypatch.setattr('salus_scan_worker.time.sleep', lambda _: None)
    try:
        poll_once(queue_client=queue, process_event=process_event)
    except DeadlockDetected:
        pass
    else:
        assert False, 'Exhausted deadlocks must surface as a failed run'
    assert calls == ['event-1'] * 3
    assert queue.deleted == []


def test_scheduled_result_worker_failure_redacts_sensitive_exception(capsys):
    def fail():
        raise RuntimeError('private/member/path?sig=secret')

    assert main(poll=fail, reconcile=lambda: None) == 1
    output = capsys.readouterr().out
    assert 'private/member' not in output
    assert 'secret' not in output
    assert '"error_type": "RuntimeError"' in output
    assert '"failure_phase": "poll"' in output
    assert main(poll=lambda: 'Held', reconcile=lambda: None) == 2
    assert json.loads(capsys.readouterr().out) == {
        'scan_result_job': 'completed', 'outcome': 'Held'}
    assert main(poll=lambda: 'Acknowledged', reconcile=lambda: None) == 0
    assert json.loads(capsys.readouterr().out) == {
        'scan_result_job': 'completed', 'outcome': 'Acknowledged'}
    assert main(poll=lambda: 'Empty', reconcile=lambda: None) == 0
    assert json.loads(capsys.readouterr().out) == {
        'scan_result_job': 'completed', 'outcome': 'Empty'}



def test_reconciliation_retries_only_database_deadlock(capsys):
    class DeadlockDetected(Exception):
        sqlstate = '40P01'

    calls = []
    waits = []
    def poll():
        calls.append('poll')
        return 'Empty'
    def reconcile():
        calls.append('reconcile')
        if calls.count('reconcile') < 3:
            raise DeadlockDetected('private/member/path')
    assert main(poll=poll, reconcile=reconcile, sleep=waits.append) == 0
    assert calls == ['poll', 'reconcile', 'reconcile', 'reconcile']
    assert waits == [0.25, 0.5]
    assert json.loads(capsys.readouterr().out) == {
        'scan_result_job': 'completed', 'outcome': 'Empty'}


def test_exhausted_reconciliation_deadlock_still_alerts(capsys):
    class DeadlockDetected(Exception):
        sqlstate = '40P01'

    calls = []
    def fail():
        calls.append('reconcile')
        raise DeadlockDetected('private/member/path')
    assert main(poll=lambda: 'Empty', reconcile=fail, sleep=lambda _: None) == 1
    assert len(calls) == 3
    output = capsys.readouterr().out
    assert 'private/member' not in output
    assert json.loads(output) == {
        'error_type': 'DeadlockDetected', 'failure_phase': 'reconcile',
        'scan_result_job': 'failed'}


def test_queue_processing_deadlock_is_not_hidden_by_retry(capsys):
    class DeadlockDetected(Exception):
        sqlstate = '40P01'

    def fail():
        raise DeadlockDetected('unacknowledged result')
    assert main(poll=fail, reconcile=lambda: None, sleep=lambda _: None) == 1
    assert json.loads(capsys.readouterr().out) == {
        'scan_result_job': 'failed', 'failure_phase': 'poll',
        'error_type': 'DeadlockDetected'}


def test_web_and_worker_select_separate_quarantine_identities(monkeypatch):
    import app
    from salus_scan_quarantine import QuarantineError

    selected = []
    monkeypatch.setenv('SALUS_SCAN_QUARANTINE_URL',
                       'https://salusquarantine.blob.core.windows.net')
    monkeypatch.setenv('AZURE_CLIENT_ID', 'web-runtime-id')
    monkeypatch.setenv('SALUS_SCAN_MANAGED_IDENTITY_CLIENT_ID', 'worker-reader-id')
    monkeypatch.setattr(app, 'AzureScanQuarantine',
                        lambda url, *, managed_identity_client_id:
                        selected.append((url, managed_identity_client_id)))
    app.package_quarantine()
    app.package_quarantine(for_worker=True)
    assert selected == [
        ('https://salusquarantine.blob.core.windows.net', 'web-runtime-id'),
        ('https://salusquarantine.blob.core.windows.net', 'worker-reader-id'),
    ]
    monkeypatch.delenv('AZURE_CLIENT_ID')
    try:
        app.package_quarantine()
    except QuarantineError:
        pass
    else:
        assert False, 'Web upload must refuse an unspecified managed identity'

