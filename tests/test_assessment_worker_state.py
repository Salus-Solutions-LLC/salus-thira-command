import tempfile
import unittest
from pathlib import Path

from assessment_worker_state import AssessmentQueue
from assessment_worker_runner import TaskResult, run_one


class Clock:
    def __init__(self):
        self.value = 1000.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class AssessmentWorkerStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / 'queue.db'
        self.clock = Clock()
        self.q = AssessmentQueue(self.db, clock=self.clock)
        self.q.add_package('pkg-a', 'tenant-a', 'engagement-a', 1)
        self.q.add_item('item-a', 'pkg-a', 'tenant-a', 'source-01', 'source', 10,
                        'opaque-evidence-ref', 'a' * 64)

    def tearDown(self):
        self.q.close()
        self.temp.cleanup()

    def test_interrupted_item_recovers_checkpoint_once(self):
        first = self.q.claim('tenant-a', 'worker-1', lease_seconds=10)
        self.assertEqual(first.attempts, 1)
        self.q.checkpoint(first, 'worker-1', {'page': 2}, lease_seconds=10)
        self.q.close()
        self.clock.advance(11)
        self.q = AssessmentQueue(self.db, clock=self.clock)
        recovered = self.q.claim('tenant-a', 'worker-2', lease_seconds=10)
        self.assertEqual(recovered.checkpoint, {'page': 2})
        self.assertEqual(recovered.attempts, 2)
        with self.assertRaises(RuntimeError):
            self.q.finish(first, 'worker-1', 'artifact-a', 'b' * 64)
        self.assertTrue(self.q.finish(recovered, 'worker-2', 'artifact-a', 'b' * 64))
        self.assertFalse(self.q.finish(recovered, 'worker-2', 'artifact-a', 'b' * 64))
        self.assertIsNone(self.q.claim('tenant-a', 'worker-3'))
        events = self.q.events('tenant-a', 'pkg-a')
        self.assertEqual([e['event_type'] for e in events],
                         ['claimed', 'checkpointed', 'recovered', 'claimed', 'complete'])

    def test_tenant_isolation_and_single_package_writer(self):
        self.q.add_package('pkg-b', 'tenant-b', 'engagement-b', 1)
        self.q.add_item('item-b', 'pkg-b', 'tenant-b', 'source-01', 'source', 10,
                        'opaque-evidence-ref-b', 'c' * 64)
        self.q.add_item('item-a2', 'pkg-a', 'tenant-a', 'analysis-01', 'analysis', 9,
                        'opaque-claim-ref', 'd' * 64)
        first = self.q.claim('tenant-a', 'worker-a')
        self.assertEqual(first.item_id, 'item-a')
        self.assertIsNone(self.q.claim('tenant-a', 'worker-a2'))
        second = self.q.claim('tenant-b', 'worker-b')
        self.assertEqual(second.item_id, 'item-b')
        self.assertEqual(len(self.q.events('tenant-b', 'pkg-a')), 0)
        with self.assertRaises(ValueError):
            self.q.add_item('bad', 'pkg-a', 'tenant-b', 'x', 'source', 1, 'x')

    def test_idempotency_and_bounded_retry(self):
        self.q.add_item('item-a', 'pkg-a', 'tenant-a', 'source-01', 'source', 10,
                        'opaque-evidence-ref', 'a' * 64)
        with self.assertRaises(ValueError):
            self.q.add_item('item-a', 'pkg-a', 'tenant-a', 'source-01', 'source', 10,
                            'different-evidence', 'a' * 64)
        with self.assertRaises(ValueError):
            self.q.add_item('leak', 'pkg-a', 'tenant-a', 'leak', 'source', 1,
                            'C:/member/private/file.pdf', 'a' * 64)
        for n in (1, 2, 3):
            item = self.q.claim('tenant-a', 'worker-a', lease_seconds=10)
            self.assertEqual(item.attempts, n)
            state = self.q.fail_retryable(item, 'worker-a', 'TEST_ERROR',
                                          delay_seconds=5, max_attempts=3)
            self.assertEqual(state, 'failed_escalated' if n == 3 else 'retry_wait')
            self.clock.advance(6)
        self.assertIsNone(self.q.claim('tenant-a', 'worker-a'))

    def test_one_gated_item_does_not_stop_independent_work(self):
        self.q.add_item('item-a2', 'pkg-a', 'tenant-a', 'independent-source', 'source', 5,
                        'opaque-evidence-ref-2', 'e' * 64)
        first = self.q.claim('tenant-a', 'worker-a')
        self.q.block(first, 'worker-a', 'blocked_access', 'SOURCE_PERMISSION_PENDING')
        second = self.q.claim('tenant-a', 'worker-a')
        self.assertEqual(second.item_id, 'item-a2')

    def test_repeated_process_loss_escalates_and_other_work_continues(self):
        self.q.add_item('item-a2', 'pkg-a', 'tenant-a', 'independent-source', 'source', 5,
                        'opaque-evidence-ref-2', 'e' * 64)
        for attempt in (1, 2, 3):
            item = self.q.claim('tenant-a', f'worker-{attempt}', lease_seconds=10)
            self.assertEqual((item.item_id, item.attempts), ('item-a', attempt))
            self.q.close()
            self.clock.advance(11)
            self.q = AssessmentQueue(self.db, clock=self.clock)
        next_item = self.q.claim('tenant-a', 'worker-4', lease_seconds=10)
        self.assertEqual(next_item.item_id, 'item-a2')
        events = self.q.events('tenant-a', 'pkg-a')
        self.assertEqual([e['event_type'] for e in events].count('failed_escalated'), 1)
        self.assertIsNone(self.q.claim('tenant-a', 'worker-5'))

    def test_runner_processes_checkpoint_and_fails_closed_without_adapter(self):
        self.assertTrue(run_one(self.q, 'tenant-a', 'worker-a', {}))
        self.assertEqual(self.q.events('tenant-a', 'pkg-a')[-1]['event_type'], 'blocked_expertise')
        self.q.add_item('item-a2', 'pkg-a', 'tenant-a', 'independent-source', 'source', 5,
                        'opaque-evidence-ref-2', 'e' * 64)

        def source_handler(item, checkpoint):
            checkpoint({'page': 1, 'source_sha256': item.source_sha256})
            return TaskResult('opaque-output-ref', 'f' * 64, review_required=True)

        self.assertTrue(run_one(self.q, 'tenant-a', 'worker-a', {'source': source_handler}))
        self.assertIsNone(self.q.claim('tenant-a', 'worker-a'))
        self.assertEqual(self.q.events('tenant-a', 'pkg-a')[-1]['event_type'], 'review_required')


if __name__ == '__main__':
    unittest.main()

