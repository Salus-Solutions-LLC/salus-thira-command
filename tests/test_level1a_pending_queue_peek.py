"""Fixed-category proof for the protected read-only scanner diagnostic."""

import base64
import json
from types import SimpleNamespace

from tools.level1a_pending_queue_peek import classify, decode_events


def test_queue_peek_distinguishes_exact_event_without_emitting_identifiers():
    row = {'blob_uri': 'https://example.invalid/private-object',
           'etag': '"0xABC123"', 'content_sha256': 'a' * 64}
    topic = '/subscriptions/example/topic'
    event = {'eventType': 'Microsoft.Security.MalwareScanningResult',
             'topic': topic,
             'data': {'blobUri': row['blob_uri'], 'eTag': '0xABC123',
                      'scanResultType': 'No threats found'}}
    content = base64.b64encode(json.dumps(event).encode()).decode()
    counts = classify([SimpleNamespace(content=content)], row, topic)
    assert counts['same_uri'] == 1
    assert counts['qualified_match'] == 1
    assert counts['result_Clean'] == 1
    assert row['blob_uri'] not in json.dumps(counts)


def test_queue_peek_holds_mismatch_and_rejects_oversized_content():
    row = {'blob_uri': 'https://example.invalid/private-object',
           'etag': '0xABC123', 'content_sha256': 'b' * 64}
    topic = '/subscriptions/example/topic'
    event = {'eventType': 'Microsoft.Security.MalwareScanningResult',
             'topic': topic,
             'data': {'blobUri': row['blob_uri'], 'eTag': '0xOTHER',
                      'scanResultType': 'No threats found'}}
    counts = classify([SimpleNamespace(content=json.dumps(event))], row, topic)
    assert counts['etag_mismatch'] == 1
    assert counts['qualified_match'] == 0
    assert decode_events('x' * 65537) is None
