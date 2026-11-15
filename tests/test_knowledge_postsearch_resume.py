"""Receipt-preserving, source-guarded continuation of the verified partial state."""
import contextlib
import base64
import copy
import importlib.util
import io
import os
from pathlib import Path
import unittest
from tools import live_knowledge_postsearch_resume as resume
from tools import live_knowledge_recovery_plan as old

spec=importlib.util.spec_from_file_location('prior_planning_fixture', Path(__file__).with_name('test_knowledge_recovery_plan.py'))
prior=importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)


class ContinuationTests(unittest.TestCase):
    connect=prior.PlanningTests.connect
    insert=prior.PlanningTests.insert
    tearDown=prior.PlanningTests.tearDown

    def setUp(self):
        prior.PlanningTests.setUp(self)
        self.conn.execute('CREATE TABLE m365_knowledge_consideration_receipts(receipt_id TEXT,query_sha256 TEXT,boundary_count INTEGER,considered_count INTEGER,matched_count INTEGER,content_available_count INTEGER,metadata_only_count INTEGER,governed_hold_count INTEGER,actor TEXT,created_at TEXT)')
        for row in resume.EXPECTED_RECEIPTS:
            keys=list(row)
            self.conn.execute('INSERT INTO m365_knowledge_consideration_receipts('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',tuple(row.values()))
        self.conn.commit()
        self.receipts_before=[dict(r) for r in self.conn.execute('SELECT * FROM m365_knowledge_consideration_receipts ORDER BY actor').fetchall()]
        self.conn.commit()
        resume.COMMIT_ACKNOWLEDGED=resume.COMMIT_ATTEMPTED=0

    def preview(self):
        value=resume.read_evidence(self.conn)
        self.conn.commit()
        return value

    def prepare(self, preview, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return resume.prepare_atomic(resume.PlanningConnection(self.conn), preview, self.inventory,
                expected_baseline=resume.baseline_digest(preview),expected_cohorts=prior.COHORTS,expected_discrepancies=1,**kwargs)

    def test_decoded_projection_preserves_old_exact_metadata_semantics(self):
        self.assertEqual(resume.read_evidence(self.conn),old.read_evidence(self.conn))

    def test_old_guard_stops_after_benign_checkpoint_movement_but_new_guard_commits_fresh_state(self):
        preview=self.preview()
        old_plan=old.make_plan(preview,self.inventory,clock=prior.CLOCK,expected_cohorts=prior.COHORTS,expected_discrepancies=1)
        self.conn.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1 WHERE candidate_id=1')
        self.conn.commit()
        with self.assertRaises(old.CensusFailure) as caught: old.save_plan(self.conn,preview,old_plan)
        self.assertEqual(caught.exception.code,'PLAN_08')
        plan,current=self.prepare(preview)
        self.assertEqual(plan['continuation']['observed_scheduling_refresh']['extraction_checkpoints'],1)
        record=next(r for b in plan['batches'] for r in b['records'] if r['source_item_id']=='s1')
        self.assertEqual(record['candidate_versions'][0]['checkpoint']['attempts'],9)
        self.assertEqual(resume.COMMIT_ATTEMPTED,1)
        self.assertEqual(resume.COMMIT_ACKNOWLEDGED,1)
        fresh=self.connect()
        try:
            wrapped=resume.PlanningConnection(fresh)
            checksum,refresh=resume.independent_readback(wrapped,plan,current)
            self.assertEqual(len(checksum),64)
            self.assertEqual(refresh['extraction_checkpoints'],0)
            self.assertEqual([dict(r) for r in fresh.execute('SELECT * FROM m365_knowledge_consideration_receipts ORDER BY actor').fetchall()],self.receipts_before)
        finally: fresh.close()

    def test_postcommit_checkpoint_movement_does_not_turn_exact_saved_plan_into_failed_readback(self):
        preview=self.preview()
        plan,current=self.prepare(preview)
        self.conn.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1 WHERE candidate_id=2')
        self.conn.commit()
        fresh=self.connect()
        try:
            _,refresh=resume.independent_readback(resume.PlanningConnection(fresh),plan,current)
            self.assertEqual(refresh['extraction_checkpoints'],1)
        finally: fresh.close()

    def test_source_version_hold_and_bulk_authority_drift_each_prevent_a_commit(self):
        preview=self.preview()
        changes=(('UPDATE m365_knowledge_candidates SET source_etag=? WHERE id=1','v2',
                  "UPDATE m365_knowledge_candidates SET source_etag='v1' WHERE id=1"),
                 ('UPDATE m365_knowledge_holds SET hold_reason=?','changed',
                  "UPDATE m365_knowledge_holds SET hold_reason='PRIVATE-REASON'"),
                 ('UPDATE m365_bulk_items SET status=? WHERE item_id=\'s1\'','Pending',
                  "UPDATE m365_bulk_items SET status='Assignment Required' WHERE item_id='s1'"))
        for sql,value,restore in changes:
            self.conn.execute(sql,(value,)); self.conn.commit()
            with self.assertRaises(resume.CensusFailure) as caught: self.prepare(preview)
            self.assertEqual(caught.exception.code,'SOURCE_CORE_DRIFT')
            self.assertEqual(resume.COMMIT_ATTEMPTED,0)
            self.conn.execute(restore); self.conn.commit()

    def test_receipt_corruption_stops_without_replacing_or_creating_receipts(self):
        preview=self.preview()
        self.conn.execute("UPDATE m365_knowledge_consideration_receipts SET matched_count=0 WHERE receipt_id=?",(resume.EXPECTED_RECEIPTS[0]['receipt_id'],))
        self.conn.commit()
        with self.assertRaises(resume.CensusFailure) as caught:self.prepare(preview)
        self.assertEqual(caught.exception.code,'RECEIPT_PRESTATE')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)

    def test_source_and_receipt_mutations_are_rejected_even_when_planning_writes_are_enabled(self):
        c=resume.PlanningConnection(self.conn)
        c.writes_enabled=True
        for sql in ("UPDATE m365_knowledge_candidates SET source_etag='bad'",'DELETE FROM m365_bulk_extraction_checks',
                    'INSERT INTO m365_knowledge_consideration_receipts VALUES(1)',
                    'WITH x AS (DELETE FROM m365_knowledge_holds RETURNING *) SELECT * FROM x',
                    'SELECT 1; DELETE FROM m365_knowledge_holds'):
            with self.assertRaises(resume.CensusFailure) as caught:c.execute(sql)
            self.assertEqual(caught.exception.code,'QUERY_DENIED')

    def test_atomic_rollback_and_repeat_attempt_guard_preserve_exact_four_receipts(self):
        preview=self.preview()
        with self.assertRaises(resume.CensusFailure):self.prepare(preview,fail_after_batches=True)
        with contextlib.redirect_stdout(io.StringIO()):resume.target_empty(resume.PlanningConnection(self.conn))
        self.conn.commit()
        self.prepare(preview)
        with self.assertRaises(resume.CensusFailure) as caught:self.prepare(preview)
        self.assertEqual(caught.exception.code,'TARGET_NOT_EMPTY')
        self.assertEqual([dict(r) for r in self.conn.execute('SELECT * FROM m365_knowledge_consideration_receipts ORDER BY actor').fetchall()],self.receipts_before)

    def test_total_lock_window_budget_rolls_back_before_commit(self):
        preview=self.preview()
        values=iter((0,61))
        with self.assertRaises(resume.CensusFailure) as caught:self.prepare(preview,monotonic=lambda:next(values))
        self.assertEqual(caught.exception.code,'TRANSACTION_BUDGET')
        self.assertEqual(resume.COMMIT_ATTEMPTED,0)

    def test_ambiguous_commit_is_not_mislabeled_as_zero_writes(self):
        preview=self.preview()
        class AcknowledgmentLost:
            backend=getattr(self.conn,'backend','sqlite')
            def __init__(self,inner):self.inner=inner
            def execute(self,*a,**k):return self.inner.execute(*a,**k)
            def rollback(self):return self.inner.rollback()
            def commit(self):self.inner.commit();raise ConnectionError('PRIVATE ENDPOINT')
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConnectionError):resume.prepare_atomic(resume.PlanningConnection(AcknowledgmentLost(self.conn)),preview,self.inventory,
                expected_baseline=resume.baseline_digest(preview),expected_cohorts=prior.COHORTS,expected_discrepancies=1)
        self.assertEqual(resume.COMMIT_ATTEMPTED,1)
        self.assertEqual(resume.COMMIT_ACKNOWLEDGED,0)
        fresh=self.connect()
        try:self.assertEqual(fresh.execute('SELECT COUNT(*) FROM m365_knowledge_recovery_plans').fetchone()[0],1)
        finally:fresh.close()

    def test_result_telemetry_does_not_expose_source_metadata(self):
        preview=self.preview()
        plan,current=self.prepare(preview)
        checksum=resume.verify_plan(self.conn,plan)
        with contextlib.redirect_stdout(io.StringIO()) as out:resume.emit_result(plan,checksum,{'extraction_checkpoints':0,'bulk_checkpoints':0})
        self.assertNotIn('PRIVATE',out.getvalue())
        self.assertNotIn('source_item_id',out.getvalue())
        self.assertIn('POSTSEARCH_NEW_SEARCH_RECEIPTS=0',out.getvalue())

    def test_history_binding_rejects_private_fields_and_wrong_original_operation(self):
        from tools import knowledge_postsearch_history as history
        value=history.reduce_history([])
        encoded=lambda v:base64.b64encode(resume.canonical(v).encode()).decode()
        self.assertEqual(resume.decode_history(encoded(value))['query_state'],'NO_FAILURE_MARKER')
        for key,bad in (('failure_stage','private_source_name'),('failure_code','PRIVATE_TOKEN'),('original_run_id',123)):
            changed=copy.deepcopy(value);changed[key]=bad
            with self.assertRaises(resume.CensusFailure):resume.decode_history(encoded(changed))


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLContinuationTests(ContinuationTests):
    def connect(self):
        from database import connect_database
        return connect_database()

    def setUp(self):
        assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        c=self.connect()
        for t in (*resume.PLAN_TABLES,*resume.SOURCE_TABLES,resume.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+t)
        c.commit();c.close()
        super().setUp()

    def tearDown(self):
        self.conn.rollback()
        for t in (*resume.PLAN_TABLES,*resume.SOURCE_TABLES,resume.RECEIPT_TABLE):self.conn.execute('DROP TABLE IF EXISTS '+t)
        self.conn.commit();self.conn.close();self.folder.cleanup()

    def test_active_source_writer_fails_nowait_and_leaves_ledger_empty(self):
        preview=self.preview()
        other=self.connect()
        try:
            other.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1 WHERE candidate_id=1')
            with self.assertRaises(Exception) as caught:self.prepare(preview)
            self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03')
            other.rollback()
            with contextlib.redirect_stdout(io.StringIO()):resume.target_empty(resume.PlanningConnection(self.conn))
        finally:other.close()


if __name__=='__main__':unittest.main()
