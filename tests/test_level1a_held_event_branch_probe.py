"""Bound the payload parser used by the one-time held-event check."""

import base64
import json

from tools.level1a_held_event_branch_probe import decode_events


def test_held_event_parser_accepts_one_wrapped_event():
    event = {'id': 'fictional-id', 'data': {'scanResultType': 'No threats found'}}
    content = base64.b64encode(json.dumps(event).encode()).decode()
    assert decode_events(content) == [event]


def test_held_event_parser_rejects_unbounded_or_malformed_input():
    assert decode_events('x' * 65537) is None
    assert decode_events(json.dumps([{}] * 11)) is None
    assert decode_events('not an event') is None
