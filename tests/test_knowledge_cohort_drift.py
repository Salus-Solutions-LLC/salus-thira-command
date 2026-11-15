"""Drift diagnostics preserve receipts and enforce database read-only access."""
import contextlib
import copy
import importlib.util
import io
import os
from pathlib import Path
import unittest
from tools import live_knowledge_cohort_drift as drift

spec = importlib.util.spec_from_file_location('continuation_fixture', Path(__file__).with_name('test_knowledge_postsearch_resume.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class DriftTests(unittest.TestCase):
    connect = fixture.ContinuationTests.connect
    insert = fixture.ContinuationTests.insert
    setUp = fixture.ContinuationTests.setUp
    tearDown = fixture.ContinuationTests.tearDown

    def observe(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return drift.observe(self.conn)

    def test_current_partition_keeps_available_exception_separate(self):
        result = self.observe()[0]
        self.assertEqual(result['REPRESENTED_FILES'], 6)
        self.assertEqual(result['UNRESOLVED_FILES'], 5)
        self.assertEqual(result['AVAILABILITY_EXCEPTIONS'], 1)
        self.assertEqual(sum(v for k,v in result.items() if k.startswith('CATEGORY_')), 5)
        self.assertEqual(result['ACCEPTED_PROJECTION_MATCH'], 0)
        self.assertNotIn('PRIVATE', str(result))

    def test_reads_use_independent_connections_and_preserve_receipts(self):
        first = self.observe()
        other = self.connect()
        try:
            with contextlib.redirect_stdout(io.StringIO()): second = drift.observe(other)
            self.assertEqual(drift.verify_pair(first, second), {'extraction_checkpoints':0,'bulk_checkpoints':0})
            self.assertEqual(second[1], 'cbb850ab8dd3a06e300b5ce2edc40764efc821a9f2fa25d4beca73d6319c01af')
        finally: other.close()

    def test_receipt_corruption_is_rejected(self):
        self.conn.execute('UPDATE m365_knowledge_consideration_receipts SET matched_count=0')
        self.conn.commit()
        with self.assertRaises(drift.support.CensusFailure): self.observe()

    def test_current_growth_changes_count_and_projection_without_adopting_baseline(self):
        evidence = drift.support.read_evidence(self.conn)
        before = drift.summarize(evidence)
        evidence['represented'].append('NEW-PRIVATE-SOURCE')
        after = drift.summarize(evidence)
        self.assertEqual(after['UNRESOLVED_FILES'], before['UNRESOLVED_FILES']+1)
        self.assertEqual(after['CATEGORY_NO_CANDIDATE'], 1)
        self.assertNotEqual(before['PROJECTION_SHA256'], after['PROJECTION_SHA256'])
        self.assertEqual(after['ACCEPTED_PROJECTION_MATCH'], 0)

    def test_core_drift_rejected_but_scheduling_movement_reported(self):
        first = self.observe()
        second = copy.deepcopy(first)
        second[2]['checks'][0]['attempts'] += 1
        self.assertEqual(drift.verify_pair(first, second)['extraction_checkpoints'], 1)
        second[0]['REPRESENTED_FILES'] += 1
        with self.assertRaisesRegex(ValueError, 'INDEPENDENT_CORE_DRIFT'): drift.verify_pair(first, second)

    def test_facade_rejects_mutations_and_multiple_statements(self):
        conn = drift.ReadOnlyConnection(self.conn)
        for sql in ('DELETE FROM m365_knowledge_holds', 'CREATE TABLE x(a TEXT)',
                    'WITH x AS (DELETE FROM m365_knowledge_holds RETURNING *) SELECT * FROM x',
                    'SELECT 1; DELETE FROM m365_knowledge_holds', 'SELECT * INTO x FROM m365_knowledge_holds',
                    'CALL private_function()', 'COMMIT', 'LOCK TABLE m365_knowledge_holds'):
            with self.assertRaisesRegex(ValueError, 'QUERY_DENIED'): conn.execute(sql)

    def test_database_itself_rejects_writes_after_observation(self):
        self.observe()
        with self.assertRaises(Exception): self.conn.execute('DELETE FROM m365_knowledge_holds')


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLDriftTests(DriftTests):
    connect = fixture.PostgreSQLContinuationTests.connect

    def setUp(self):
        assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        conn = self.connect()
        for table in (*drift.support.PLAN_TABLES,*drift.support.SOURCE_TABLES,drift.support.RECEIPT_TABLE):
            conn.execute('DROP TABLE IF EXISTS '+table)
        conn.commit(); conn.close()
        DriftTests.setUp(self)

    def tearDown(self):
        self.conn.rollback()
        for table in (*drift.support.PLAN_TABLES,*drift.support.SOURCE_TABLES,drift.support.RECEIPT_TABLE):
            self.conn.execute('DROP TABLE IF EXISTS '+table)
        self.conn.commit(); self.conn.close(); self.folder.cleanup()


if __name__=='__main__': unittest.main()
