"""Planning is atomic, baseline-correlated, non-executing and receipt-preserving."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from tools import live_knowledge_approved_recovery_plan as planner
from tools import knowledge_recovery_plan_payload as payload
baseline=planner.baseline
support=baseline.support
spec=importlib.util.spec_from_file_location('approved_baseline_fixture',Path(__file__).with_name('test_knowledge_baseline_proposal.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class PlanningTests(unittest.TestCase):
    connect=fixture.BaselineTests.connect
    insert=fixture.BaselineTests.insert
    build=fixture.BaselineTests.build
    save=fixture.BaselineTests.save
    tearDown=fixture.BaselineTests.tearDown

    def setUp(self):
        fixture.BaselineTests.setUp(self)
        self.header,self.members,self.core=self.build()
        self.save(self.header,self.members,self.core)
        self.manifest=support.digest(self.header)
        conn=baseline.ProposalConnection(self.conn)
        self.context={'evidence':support.read_evidence(conn),'families':{f:baseline.search_matrix(conn,family=f) for f in ('C','B','H')},
                      'inventory':self.inventory,'drive_id':'PRIVATE-DRIVE','expected':fixture.fixture.prior.COHORTS,'expected_exceptions':1}
        self.conn.commit()

    def prepare(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            result=planner.prepare(self.conn,self.header,self.members,self.core,self.context,expected_manifest=self.manifest,**kwargs)
        self.assertNotIn('PRIVATE',output.getvalue())
        return result

    def test_exact_baseline_eight_receipts_and_fresh_connection_plan_readback(self):
        old=[dict(r) for r in self.conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor').fetchall()];self.conn.commit()
        plan,members,core=self.prepare()
        other=self.connect()
        try:
            conn=baseline.begin_read_only(other)
            self.assertEqual(planner.read_baseline(conn,self.manifest),(self.header,self.members))
            checksum=planner.verify(conn,plan,self.header,self.members,core,expected_manifest=self.manifest)
            self.assertEqual(len(checksum),64)
            current=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor').fetchall()]
            self.assertTrue(all(row in current for row in old));self.assertEqual(len(current),12)
        finally:other.close()
        records=[r for b in plan['batches'] for r in b['records']]
        self.assertEqual(len(records),5);self.assertEqual(len({r['source_item_id'] for r in records}),5)
        self.assertEqual(len(plan['availability_exceptions']),1)
        self.assertTrue(all(b['record_count']<=50 and not b['processing_authorized'] for b in plan['batches']))
        self.assertTrue(all(not r['processing_authorized'] for r in records))
        self.assertIn('separate',next(r['required_gate'] for r in records if r['category']=='automatic_retry'))
        self.assertIn('preserve hold',next(r['required_gate'] for r in records if r['category']=='governed_hold'))

    def test_timestamp_and_scheduling_refresh_preserves_authority_and_source_records(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='current review clock' WHERE id=1")
        self.conn.execute("UPDATE m365_bulk_items SET attempts=7,next_attempt=999,reason='current metadata'")
        self.conn.commit()
        plan,_,_=self.prepare()
        self.assertTrue(plan['approved_baseline']['paused_retries_preserved'])
        self.assertTrue(all(r['attempts']==7 for b in plan['batches'] for s in b['records'] for r in s['bulk_checkpoints']))

    def test_classification_rights_change_rejected_without_planning_writes(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET classification_json=classification_json || ' ' WHERE id=1");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'APPROVED_SOURCE_RIGHTS_VERSION_DRIFT'):self.prepare()
        self.assertEqual((planner.COMMIT_ATTEMPTED,planner.COMMIT_ACKNOWLEDGED),(0,0))

    def test_equal_total_swapped_membership_is_rejected(self):
        changed=copy.deepcopy(self.members)
        changed[0]['category'],changed[1]['category']=changed[1]['category'],changed[0]['category']
        with self.assertRaisesRegex(ValueError,'APPROVED_SOURCE_RIGHTS_VERSION_DRIFT'):planner.approved_scope(self.members,changed)

    def test_baseline_member_tamper_and_receipt_tamper_rejected(self):
        self.conn.execute('UPDATE '+baseline.TABLES[1]+" SET payload_json=payload_json || ' ' WHERE source_item_id='s1'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'BASELINE_MEMBER_DRIFT'):self.prepare()

    def test_preserved_new_receipt_tamper_is_rejected(self):
        receipt=self.header['new_receipts'][0]['receipt_id']
        self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(receipt,));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'PRESERVED_RECEIPT_DRIFT'):self.prepare()

    def test_atomic_rollback_leaves_eight_receipts_and_no_plan(self):
        with self.assertRaisesRegex(ValueError,'INJECTED_ROLLBACK'):self.prepare(fail_after_batches=True)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],8)
        with contextlib.redirect_stdout(io.StringIO()):support.target_empty(planner.PlanConnection(self.conn))

    def test_duplicate_preparation_is_rejected(self):
        self.prepare()
        with self.assertRaises(support.CensusFailure):self.prepare()

    def test_lost_commit_acknowledgement_does_not_claim_zero_writes(self):
        class Lost:
            backend=getattr(self.conn,'backend','sqlite')
            def execute(obj,*args):return self.conn.execute(*args)
            def commit(obj):self.conn.commit();raise ConnectionError('PRIVATE')
            def rollback(obj):self.conn.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConnectionError):planner.prepare(Lost(),self.header,self.members,self.core,self.context,expected_manifest=self.manifest)
        self.assertEqual((planner.COMMIT_ATTEMPTED,planner.COMMIT_ACKNOWLEDGED),(1,0))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.PLAN_TABLES[0]).fetchone()[0],1)

    def test_mutation_facade_rejects_source_receipt_baseline_edits(self):
        conn=planner.PlanConnection(self.conn);conn.writes_enabled=True
        for sql in ('DELETE FROM '+support.RECEIPT_TABLE,'UPDATE m365_knowledge_candidates SET status=\'Bad\'',
                    'INSERT INTO '+baseline.TABLES[0]+' VALUES(?,?,?,?,?)','SELECT 1; DELETE FROM m365_bulk_items',
                    'WITH x AS (DELETE FROM m365_knowledge_holds RETURNING *) SELECT * FROM x','CREATE TABLE arbitrary(a TEXT)'):
            with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):conn.execute(sql)

    def test_unresolved_identity_version_drift_rejected(self):
        self.conn.execute("UPDATE m365_bulk_items SET etag='v2' WHERE item_id='s1'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_IDENTITY_VERSION_DRIFT'):self.prepare()

    def test_current_hold_disposition_cannot_borrow_baseline_approval(self):
        self.conn.execute("UPDATE m365_knowledge_holds SET citation_disposition='new disposition'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'APPROVED_SOURCE_RIGHTS_VERSION_DRIFT'):self.prepare()

    def test_deadline_exhaustion_rolls_back_before_writes(self):
        count=0
        def clock():
            nonlocal count
            count+=1
            return 0 if count==1 else 61
        with self.assertRaisesRegex(ValueError,'TRANSACTION_BUDGET'):self.prepare(clock=clock)
        self.assertEqual(planner.COMMIT_ATTEMPTED,0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],8)

    def test_readback_reports_later_review_clock_but_rejects_rights_change(self):
        plan,_,core=self.prepare()
        self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='later' WHERE id=1");self.conn.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            planner.verify(planner.PlanConnection(self.conn),plan,self.header,self.members,core,expected_manifest=self.manifest)
        self.conn.execute("UPDATE m365_knowledge_candidates SET decision='changed rights' WHERE id=1");self.conn.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'INDEPENDENT_SOURCE_DRIFT'):
                planner.verify(planner.PlanConnection(self.conn),plan,self.header,self.members,core,expected_manifest=self.manifest)

    def test_current_task_receipt_tamper_fails_independent_verification(self):
        plan,_,core=self.prepare()
        receipt=plan['current_consideration']['receipts'][0]['receipt_id']
        self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(receipt,));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'TASK_RECEIPT_DRIFT'):
            planner.verify(planner.PlanConnection(self.conn),plan,self.header,self.members,core,expected_manifest=self.manifest)

    def test_missing_sources_and_fifty_record_limit_do_not_authorize_processing(self):
        evidence=copy.deepcopy(self.context['evidence']);expected=copy.deepcopy(self.context['expected'])
        template=copy.deepcopy(evidence['candidates'][0])
        for index in range(101):
            row={**template,'id':1000+index,'source_item_id':'synthetic-'+str(index)}
            evidence['candidates'].append(row);evidence['represented'].append(row['source_item_id'])
        evidence['represented']+=['missing-a','missing-b']
        expected['governed_review']+=101;expected['no_candidate']+=2
        plan=support.make_plan(evidence,self.inventory,clock=1,expected_cohorts=expected,expected_discrepancies=1)
        self.assertEqual(plan['summary']['prepared_sources'],108)
        self.assertTrue(all(0<b['record_count']<=50 for b in plan['batches']))
        missing=[r for b in plan['batches'] for r in b['records'] if r['category']=='no_candidate']
        self.assertEqual(len(missing),2);self.assertTrue(all(not r['processing_authorized'] and not r['candidate_versions'] for r in missing))


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLPlanningTests(PlanningTests):
    connect=fixture.fixture.PostgreSQLContinuationTests.connect
    def setUp(self):
        c=self.connect()
        for table in (*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+table)
        c.commit();c.close();PlanningTests.setUp(self)
    tearDown=fixture.PostgreSQLBaselineTests.tearDown

    def test_active_checkpoint_writer_stops_before_plan_and_receipts(self):
        other=self.connect()
        try:
            other.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1')
            with self.assertRaises(Exception) as caught:self.prepare()
            self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03')
            self.assertEqual(planner.COMMIT_ATTEMPTED,0)
        finally:other.rollback();other.close()


class PayloadTests(unittest.TestCase):
    def test_source_bundle_fits_single_argument_and_pins_all_three_modules(self):
        import base64,hashlib,zlib
        root=Path(__file__).resolve().parent.parent
        encoded,checksum=payload.bundle(root)
        raw=zlib.decompress(base64.b64decode(encoded))
        self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum)
        modules=json.loads(raw)
        self.assertEqual([m['name'] for m in modules],[m[0] for m in payload.MODULES])
        for module in modules:
            code=base64.b64decode(module['source'])
            self.assertEqual(hashlib.sha256(code).hexdigest(),module['sha256'])
            compile(code,'<reviewed-bundle>','exec')
        self.assertLess(len(encoded)+4096,128000)


if __name__=='__main__':unittest.main()
