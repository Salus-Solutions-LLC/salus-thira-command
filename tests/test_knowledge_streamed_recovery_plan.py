"""Planning is atomic, baseline-correlated, non-executing and receipt-preserving."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import live_knowledge_streamed_recovery_plan as planner
from tools import knowledge_streamed_recovery_payload as payload
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

    def test_locked_planning_never_builds_a_second_full_baseline_proposal(self):
        with patch.object(baseline,'build_proposal',side_effect=AssertionError('full manifest rebuilt')):
            plan,_,_=self.prepare()
        self.assertEqual(len(plan['current_consideration']['per_source_coverage']),6)

    def test_owned_preview_buffers_are_released_before_locked_current_view(self):
        import weakref
        class Snapshot(dict):pass
        class Buffer:pass
        context=dict(self.context);context['evidence']=dict(self.context['evidence'])
        snapshot=Snapshot(self.core);snapshot_ref=weakref.ref(snapshot)
        context['preview_core']=snapshot;del snapshot
        buffer=Buffer();buffer_ref=weakref.ref(buffer)
        context['evidence']['preview_only_buffer']=buffer;del buffer
        context['_transfer_owned']=True
        actual=planner.current_view
        def view(*args,**kwargs):
            self.assertIsNone(snapshot_ref())
            self.assertIsNone(buffer_ref())
            return actual(*args,**kwargs)
        with patch.object(planner,'current_view',side_effect=view),contextlib.redirect_stdout(io.StringIO()):
            plan,_,_=planner.prepare(self.conn,self.header,self.members,None,context,expected_manifest=self.manifest)
        self.assertEqual(plan['summary']['prepared_sources'],5)
        self.assertIsNone(context['evidence']);self.assertIsNone(context['families'])

    def test_compact_coverage_masks_reconcile_all_four_receipts_and_no_match_sources(self):
        plan,_,_=self.prepare()
        observation=plan['current_consideration'];coverage=observation['per_source_coverage']
        self.assertEqual([r[0] for r in coverage],sorted(self.context['evidence']['represented']))
        self.assertEqual(observation['coverage_encoding']['query_bit_order'],[label for label,_ in baseline.QUERIES])
        self.assertTrue(observation['coverage_encoding']['all_sources_considered_by_all_queries'])
        for bit,receipt in enumerate(observation['receipts']):
            self.assertEqual(sum(bool(mask&(1<<bit)) for _,mask in coverage),receipt['matched_count'])

    def test_existing_current_task_receipt_stops_before_any_repeated_preparation(self):
        row=dict(self.header['new_receipts'][0]);row['receipt_id']='prior-attempt';row['actor']=planner.ACTOR+'membership'
        self.conn.execute('INSERT INTO '+support.RECEIPT_TABLE+' VALUES('+','.join('?' for _ in row)+')',tuple(row.values()));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'TASK_RECEIPT_DRIFT'):self.prepare()
        self.assertEqual(planner.COMMIT_ATTEMPTED,0)

    def test_decode_only_required_baseline_members_but_verify_every_legacy_payload(self):
        for table in baseline.TABLES:self.conn.execute('DROP TABLE '+table)
        self.conn.execute('DELETE FROM '+support.RECEIPT_TABLE+' WHERE actor LIKE ?',(baseline.ACTOR+'%',))
        self.conn.execute('UPDATE m365_knowledge_candidates SET classification_json=? WHERE source_item_id=?',
            (json.dumps({'extraction':{'status':'Complete','text':'fixture available text'}}),'s6'))
        self.conn.commit()
        conn=baseline.ProposalConnection(self.conn);evidence=support.read_evidence(conn);core=baseline.core_snapshot(conn)
        header,members=baseline.build_proposal(evidence,self.inventory,baseline.search_matrix(conn),core,'PRIVATE-DRIVE',expected=self.context['expected'],expected_exceptions=0)
        self.conn.commit();self.save(header,members,core)
        with contextlib.redirect_stdout(io.StringIO()):saved,selected=planner.read_baseline(planner.PlanConnection(self.conn),support.digest(header))
        self.assertEqual(len(selected),5);self.assertEqual(len(saved['member_hashes']),6)
        self.conn.execute('UPDATE '+baseline.TABLES[1]+" SET payload_json=payload_json || ' ' WHERE source_item_id='s6'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'BASELINE_MEMBER_DRIFT'):
            planner.verify_baseline(planner.PlanConnection(self.conn),saved,selected,support.digest(header))

    def test_current_view_covers_new_available_sources_without_decoding_their_members(self):
        evidence=copy.deepcopy(self.context['evidence']);core=copy.deepcopy(self.core)
        template=evidence['candidates'][-1];source=core['candidates'][-1]
        for i in range(100):
            key='extra-available-'+str(i)
            evidence['represented'].append(key);core['represented'].append(key)
            evidence['candidates'].append({**template,'id':2000+i,'source_item_id':key,'legacy_complete':1,'has_text':1,'strict_text':1,'extraction_status':'Complete'})
            core['candidates'].append({**source,'id':2000+i,'source_item_id':key})
        matrix={s:[1,0,1,0] for s in evidence['represented']}
        with contextlib.redirect_stdout(io.StringIO()):header,members=planner.current_view(evidence,self.inventory,matrix,core,'PRIVATE-DRIVE',expected=self.context['expected'],expected_exceptions=1)
        self.assertEqual(header['represented_files'],106);self.assertEqual(len(members),6)
        self.assertEqual(header['new_receipts'][0]['considered_count'],106)
        self.assertEqual(header['new_receipts'][0]['content_available_count'],101)
        self.assertNotIn('member_hashes',header)

    def test_baseline_creation_event_drift_is_rejected(self):
        self.conn.execute('UPDATE '+baseline.TABLES[2]+" SET payload_json='{}'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'BASELINE_EVENT_DRIFT'):self.prepare()

    def test_full_scale_projection_retains_8435_selected_members_and_full_23757_coverage(self):
        evidence={'represented':[],'candidates':[],'holds':[]};core={'represented':[],'candidates':[],'holds':[],'bulk':[]}
        templates={s:[r for r in self.context['evidence']['candidates'] if r['source_item_id']==s] for s in ('s1','s2','s3','s5','s6')}
        proto=self.core['candidates'][0];hold=self.core['holds'][0];serial=0
        partition=[('s1',7085),('s2',733),('s3',512),('hold',93),('s5',5),('none',2),('exception',5),('complete',15322)]
        for kind,count in partition:
            for i in range(count):
                key='scale-source-'+str(len(evidence['represented']));evidence['represented'].append(key)
                if kind=='hold':
                    h={**hold,'source_item_id':key};evidence['holds'].append(h);core['holds'].append(h);continue
                if kind=='none':continue
                rows=templates.get(kind,templates['s6'])
                for template in rows:
                    serial+=1;r={**template,'id':serial,'source_item_id':key}
                    if kind=='complete':r.update(extraction_status='Complete',has_text=1,strict_text=1,legacy_complete=1)
                    evidence['candidates'].append(r);core['candidates'].append({**proto,'id':serial,'source_item_id':key})
        core['represented']=list(evidence['represented']);matrix={s:[1,0,1,0] for s in evidence['represented']}
        inventory={s:self.inventory['s1'] for s in evidence['represented'][:-10]}
        with contextlib.redirect_stdout(io.StringIO()):header,members=planner.current_view(evidence,inventory,matrix,core,'PRIVATE-DRIVE')
        self.assertEqual(header['represented_files'],23757);self.assertEqual(header['physical_files'],23747)
        self.assertEqual(header['unresolved_files'],8430);self.assertEqual(len(members),8435)
        self.assertEqual(header['categories'],baseline.EXPECTED)
        self.assertEqual([r['considered_count'] for r in header['new_receipts']],[23757]*4)
        self.assertEqual(header['new_receipts'][1]['matched_count'],0)


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
    def test_member_payload_cursor_pages_are_bounded_and_closed_without_fetchall(self):
        selected=['source-'+str(i).zfill(4) for i in range(205)]
        class Cursor:
            def __init__(obj,keys):obj.keys=keys;obj.closed=False
            def __iter__(obj):
                for key in obj.keys:yield {'source_item_id':key,'payload_json':json.dumps({'source_item_id':key,'metadata':{'same_field':'value'}})}
            def fetchall(obj):raise AssertionError('buffered all payloads')
            def close(obj):obj.closed=True
        class Connection:
            def __init__(obj):obj.cursors=[]
            def execute(obj,sql,params):
                self.assertLessEqual(len(params),101)
                cursor=Cursor(params[1:]);obj.cursors.append(cursor);return cursor
        conn=Connection();members=list(planner.read_member_groups(conn,selected))
        self.assertEqual([m['source_item_id'] for m in members],selected)
        self.assertEqual(len(conn.cursors),3);self.assertTrue(all(c.closed for c in conn.cursors))
        self.assertIs(next(iter(members[0]['metadata'])),next(iter(members[-1]['metadata'])))

    def test_platform_exit_diagnostic_does_not_invent_oom_from_exit_137(self):
        from tools.knowledge_job_execution_diagnostic import summarize
        value={'properties':{'status':'Failed','reason':'PRIVATE PROVIDER DETAIL','template':{'env':'PRIVATE'},
            'detailedStatus':{'replicas':[{'name':'PRIVATE','containers':[{'name':'PRIVATE','code':137,'additionalInformation':'PRIVATE'}]}]}}}
        result=summarize(value)
        self.assertEqual(result['EXIT_CODES'],'137');self.assertEqual(result['OOM_EXPLICIT'],0)
        self.assertNotIn('PRIVATE',json.dumps(result))
        value['properties']['detailedStatus']['replicas'][0]['containers'][0]['additionalInformation']='OOMKilled'
        self.assertEqual(summarize(value)['OOM_EXPLICIT'],1)

    def test_peak_memory_guard_stops_with_fixed_telemetry(self):
        import sys,types
        fake=types.SimpleNamespace(RUSAGE_SELF=0,getrusage=lambda _:types.SimpleNamespace(ru_maxrss=800000))
        with patch.dict(sys.modules,{'resource':fake}),contextlib.redirect_stdout(io.StringIO()) as output:
            with self.assertRaisesRegex(ValueError,'MEMORY_BUDGET'):planner.phase('bounded_memory_fixture')
        self.assertIn('RECOVERY_PEAK_RSS_KIB=800000',output.getvalue())

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
