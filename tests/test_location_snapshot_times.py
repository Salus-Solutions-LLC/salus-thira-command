"""Independent observation times must not masquerade as source version drift."""
import copy
from datetime import datetime, timedelta, timezone
import json
import unittest
from tools.charter_task_compliance import LOCATIONS, location_checks


class SnapshotTimeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 23, 20, 0, tzinfo=timezone.utc)
        self.task = {'task_id': 'FICTIONAL-SNAPSHOT-TEST', 'locations': {}}
        self.raw = {'proof': b'Fictional content review evidence'}
        self.records = {}
        for kind in LOCATIONS:
            before = {'task_id': self.task['task_id'], 'boundary': kind + '-fictional',
                      'authority': 'Fictional authorized inventory',
                      'observed_at': (self.now - timedelta(minutes=10)).isoformat(),
                      'items': [{'id': kind + '-one', 'version': 'v1'}]}
            after = copy.deepcopy(before)
            after['observed_at'] = (self.now - timedelta(minutes=1)).isoformat()
            review = {'task_id': self.task['task_id'], 'items': [{
                'id': kind + '-one', 'version': 'v1', 'state': 'content_reviewed',
                'relevant': True, 'reason': 'Fictional source meaning checked',
                'evidence': ['proof'], 'portion_reviewed': 'Fictional complete item',
                'where_used': ['fictional decision'], 'url': 'https://example.invalid/item',
                'publisher': 'Fictional publisher', 'title': 'Fictional source',
                'accessed_at': after['observed_at']}]}
            for suffix, value in [('before', before), ('after', after), ('review', review)]:
                self.records[kind + '-' + suffix] = value
            self.task['locations'][kind] = {'state': 'considered', 'boundary': before['boundary'],
                'discovery_method': 'Fictional independent enumeration', 'before': kind + '-before',
                'after': kind + '-after', 'review': kind + '-review',
                'evidence': [kind + '-' + suffix for suffix in ('before', 'after', 'review')],
                'queries': [{'query': 'fictional source query', 'searched_at': after['observed_at'], 'evidence': ['proof']}]}

    def result(self):
        return location_checks(self.task, {**self.raw, **{k: json.dumps(v).encode()
                               for k, v in self.records.items()}}, self.now)

    def test_distinct_fresh_observation_times_with_same_inventory_pass(self):
        self.assertEqual(self.result(), set())

    def test_actual_membership_version_and_boundary_drift_still_fail(self):
        original = copy.deepcopy(self.records)
        changes = [('items', [{'id': 'changed', 'version': 'v1'}]),
                   ('items', [{'id': 'knowledge-one', 'version': 'v2'}]),
                   ('boundary', 'foreign'), ('authority', 'foreign'), ('task_id', 'foreign')]
        for key, value in changes:
            self.records = copy.deepcopy(original)
            self.records['knowledge-after'][key] = value
            with self.subTest(key=key): self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())

    def test_reversed_stale_future_naive_and_missing_after_time_fail(self):
        original = copy.deepcopy(self.records)
        bad = [(self.now - timedelta(minutes=11)).isoformat(),
               (self.now - timedelta(days=2)).isoformat(),
               (self.now + timedelta(seconds=1)).isoformat(),
               self.now.replace(tzinfo=None).isoformat(), 'bad', None]
        for stamp in bad:
            self.records = copy.deepcopy(original)
            self.records['knowledge-after']['observed_at'] = stamp
            with self.subTest(stamp=stamp): self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())
        del self.records['knowledge-after']['observed_at']
        self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())

    def test_stale_before_cannot_be_refreshed_by_current_after(self):
        self.records['knowledge-before']['observed_at'] = (self.now - timedelta(days=2)).isoformat()
        self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())

    def test_relevant_unavailable_content_still_fails(self):
        self.records['knowledge-review']['items'][0]['state'] = 'unavailable'
        self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())

    def test_missing_review_member_or_evidence_still_fails(self):
        self.records['knowledge-review']['items'] = []
        self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())
        self.records['internet-review']['items'][0]['evidence'] = ['missing']
        self.assertIn('COVERAGE_NOT_VERIFIED:internet', self.result())

    def test_other_envelope_changes_are_not_ignored(self):
        self.records['knowledge-after']['unrecognized'] = 'unreviewed change'
        self.assertIn('COVERAGE_NOT_VERIFIED:knowledge', self.result())


if __name__ == '__main__':
    unittest.main(verbosity=2)
