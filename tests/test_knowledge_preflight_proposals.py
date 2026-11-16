"""All-proposal review, bounded selection and append-only protection on real DBs."""
import contextlib,copy,importlib.util,io,json,os
from pathlib import Path
import unittest
from tools import live_knowledge_preflight_proposals as pre
spec=importlib.util.spec_from_file_location('preflight_remediation_fixture',Path(__file__).with_name('test_knowledge_remediation_proposals.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
rem=pre.rem;planning=pre.planning;baseline=pre.baseline;support=pre.support


class PreflightTests(unittest.TestCase):
    connect=fixture.RemediationTests.connect
    insert=fixture.RemediationTests.insert
    save=fixture.RemediationTests.save
    tearDown=fixture.RemediationTests.tearDown
    refresh=fixture.RemediationTests.refresh

    def build(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET source_sha256=?,source_archive_etag='archive-v1',source_archive_item_id='PRIVATE-ARCHIVE-' || source_item_id",('a'*64,));self.conn.commit()
        return fixture.RemediationTests.build(self)

    def setUp(self):
        fixture.RemediationTests.setUp(self)
        with contextlib.redirect_stdout(io.StringIO()):self.rem_header,self.saved,_=rem.prepare(self.conn,self.context,**self.args)
        self.input_sha=support.digest(self.rem_header)
        self.proof_args={**self.args,'expected_input':self.input_sha}
        self.refresh_preflight()

    def refresh_preflight(self):
        conn=pre.Connection(self.conn);core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn)
        families={f:pre.search_matrix(conn,family=f) for f in ('C','B','H')}
        base,parent,header,_=pre.input_proof(conn,**self.proof_args)
        reviews,preflights,scope,histogram=pre.review_all(conn,base,parent,header,evidence,core,self.inventory,expected_sources=5)
        self.pre_context={'preview_core':core,'evidence':evidence,'families':families,'inventory':self.inventory,'drive_id':'PRIVATE-DRIVE','reviews':reviews,'preflights':preflights,'scope':scope,'histogram':histogram}
        self.conn.commit()

    def prepare(self,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as logs:result=pre.prepare(self.conn,self.pre_context,**self.proof_args,**kwargs)
        self.assertNotIn('PRIVATE',logs.getvalue());return result

    def frozen(self):
        return {t:[dict(r) for r in self.conn.execute('SELECT * FROM '+t).fetchall()] for t in (*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES)}

    def test_all_reviews_sixteen_preserved_twenty_readback_and_no_source_writes(self):
        before=self.frozen();receipts=[dict(r) for r in self.conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor')];self.conn.commit()
        header,reviews,preflights,current=self.prepare()
        self.assertGreater(len(preflights),0)
        self.assertEqual(self.frozen(),before);self.assertEqual(header['reviewed_batches'],5);self.assertEqual(header['reviewed_sources'],5)
        self.assertEqual(sum(r['source_count'] for r in reviews),5);self.assertLessEqual(header['selected_sources'],10)
        self.assertTrue(all(not r['human_qualification_completed'] and not r['content_review_completed'] for v in reviews for r in v['sources']))
        self.assertFalse(header['preflight_execution_authorized']);self.assertFalse(header['processing_authorized'])
        other=self.connect()
        try:
            conn=baseline.begin_read_only(other);self.assertEqual(pre.verify_output(conn,header,reviews,preflights),support.digest(header))
            self.assertEqual(pre.input_proof(conn,**self.proof_args)[3],header['preserved_receipts_sha256'])
            now=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor')]
            self.assertEqual(len(now),20);self.assertTrue(all(r in now for r in receipts));self.assertEqual(baseline.core_snapshot(conn),current)
        finally:other.close()

    def test_input_raw_header_batch_and_event_integrity(self):
        self.conn.execute('UPDATE '+rem.TABLES[0]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'REMEDIATION_HEADER_DRIFT'):self.prepare()
        self.assertEqual(pre.COMMIT_ATTEMPTED,0)

    def test_input_batch_payload_integrity(self):
        self.conn.execute('UPDATE '+rem.TABLES[1]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'REMEDIATION_BATCH_DRIFT'):self.prepare()

    def test_input_event_integrity(self):
        self.conn.execute('UPDATE '+rem.TABLES[2]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'REMEDIATION_EVENT_DRIFT'):self.prepare()

    def test_all_four_newest_receipts_are_preserved(self):
        rid=self.rem_header['current_consideration']['receipts'][0]['receipt_id']
        self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(rid,));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'PRESERVED_RECEIPT_DRIFT'):self.prepare()

    def test_current_rights_or_classification_drift_is_rejected(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET decision='changed rights' WHERE id=1");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.refresh_preflight()

    def test_locked_rights_drift_rejects_before_writes(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET decision='changed rights' WHERE id=1");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.prepare()
        self.assertEqual(pre.COMMIT_ATTEMPTED,0)

    def test_review_clock_and_checkpoint_refresh_are_captured_without_mutation(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='new clock' WHERE id=1");self.conn.execute('UPDATE m365_bulk_items SET attempts=8,next_attempt=123');self.conn.commit()
        header,_,preflights,_=self.prepare();self.assertTrue(header['paused_retries_preserved'])
        self.assertTrue(all(r['attempts']==8 for p in preflights for s in p['source_bindings'] for r in s['current_bulk_checkpoints']))
        self.assertTrue(all(r['attempts']==8 for r in self.conn.execute('SELECT attempts FROM m365_bulk_items')))

    def test_current_task_masks_account_for_no_match_sources(self):
        conn=pre.Connection(self.conn);self.assertEqual(pre.search_matrix(conn),baseline.combine_families(self.pre_context['families']));self.conn.commit()
        header,_,_,_=self.prepare();obs=header['current_consideration']
        for bit,receipt in enumerate(obs['receipts']):self.assertEqual(sum(bool(v&(1<<bit)) for _,v in obs['per_source_coverage']),receipt['matched_count'])

    def test_outside_unresolved_source_is_considered_without_scope_expansion(self):
        self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER','outside-source','PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'))
        self.inventory['outside-source']=dict(self.inventory['s1']);self.conn.commit();self.refresh_preflight()
        header,reviews,_,_=self.prepare();obs=header['current_consideration']
        self.assertEqual(obs['unresolved_outside_review_scope'],['outside-source']);self.assertEqual(obs['unresolved_outside_review_scope_count'],1)
        self.assertEqual(obs['represented_files'],7);self.assertEqual(header['reviewed_sources'],5)
        self.assertNotIn('outside-source',{r['source_item_id'] for batch in reviews for r in batch['sources']})

    def test_atomic_rollback_keeps_sixteen_and_empty_target(self):
        with self.assertRaisesRegex(ValueError,'INJECTED_ROLLBACK'):self.prepare(fail_after_reviews=True)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],16)
        with contextlib.redirect_stdout(io.StringIO()):pre.target_empty(pre.Connection(self.conn))

    def test_duplicate_proposal_run_is_rejected(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'TARGET_NOT_EMPTY'):self.prepare()

    def test_deadline_aborts_before_writes(self):
        calls=0
        def clock():
            nonlocal calls
            calls+=1;return 0 if calls==1 else 61
        with self.assertRaisesRegex(ValueError,'TRANSACTION_BUDGET'):self.prepare(clock=clock)
        self.assertEqual(pre.COMMIT_ATTEMPTED,0)

    def test_missing_review_cannot_be_hidden(self):
        self.pre_context['reviews'].pop()
        with self.assertRaisesRegex(ValueError,'REVIEW_SCOPE_DRIFT'):self.prepare()

    def test_selected_paused_or_out_of_scope_source_is_rejected(self):
        self.assertTrue(self.pre_context['preflights'])
        self.pre_context['preflights'][0]['source_bindings'][0]['source_item_id']='outside-source'
        with self.assertRaisesRegex(ValueError,'PREFLIGHT_SCOPE_DRIFT'):self.prepare()

    def test_preflight_execution_flag_cannot_be_promoted(self):
        self.pre_context['preflights'][0]['preflight_execution_authorized']=True
        with self.assertRaisesRegex(ValueError,'PREFLIGHT_AUTHORITY_DRIFT'):self.prepare()

    def test_scope_budget_cannot_be_expanded(self):
        self.pre_context['preflights'][0]['bounds']={**pre.BOUNDS,'maximum_selected_sources':100}
        with self.assertRaisesRegex(ValueError,'PREFLIGHT_BOUND_DRIFT'):self.prepare()

    def test_lost_commit_ack_is_ambiguous_and_output_durable(self):
        class Lost:
            backend=getattr(self.conn,'backend','sqlite')
            def execute(obj,*a):return self.conn.execute(*a)
            def commit(obj):self.conn.commit();raise ConnectionError('PRIVATE')
            def rollback(obj):self.conn.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConnectionError):pre.prepare(Lost(),self.pre_context,**self.proof_args)
        self.assertEqual((pre.COMMIT_ATTEMPTED,pre.COMMIT_ACKNOWLEDGED),(1,0))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+pre.TABLES[0]).fetchone()[0],1)

    def test_output_tamper_is_rejected_by_exact_readback(self):
        header,reviews,preflights,_=self.prepare();self.conn.execute('UPDATE '+pre.TABLES[1]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'OUTPUT_BATCH_DRIFT'):pre.verify_output(pre.Connection(self.conn),header,reviews,preflights)

    def test_sql_facade_denies_all_preserved_record_writes_and_arbitrary_sql(self):
        conn=pre.Connection(self.conn);conn.writes_enabled=True
        tests=[('UPDATE m365_knowledge_holds SET status=\'Released\'',()),('DELETE FROM '+rem.TABLES[0],()),('INSERT INTO '+rem.TABLES[2]+' VALUES(?,?,?)',('x',)*3),
            ('INSERT INTO '+support.RECEIPT_TABLE+' VALUES(?,?,?,?,?,?,?,?,?,?)',('x',)*10),('CREATE TABLE arbitrary(a TEXT)',()),('SELECT 1; DELETE FROM '+rem.TABLES[0],()),
            ('WITH x AS (DELETE FROM m365_knowledge_candidates RETURNING *) SELECT * FROM x',())]
        for sql,args in tests:
            with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):conn.execute(sql,args)


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLPreflightTests(PreflightTests):
    connect=fixture.PostgreSQLRemediationTests.connect
    def setUp(self):
        assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        c=self.connect()
        for table in (*pre.TABLES,*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+table)
        c.commit();c.close();PreflightTests.setUp(self)
    def tearDown(self):
        self.conn.rollback()
        for table in (*pre.TABLES,*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):self.conn.execute('DROP TABLE IF EXISTS '+table)
        self.conn.commit();self.conn.close();self.folder.cleanup()
    def test_checkpoint_writer_stops_nowait_before_writes(self):
        other=self.connect()
        try:
            other.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1')
            with self.assertRaises(Exception) as caught:self.prepare()
            self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03');self.assertEqual(pre.COMMIT_ATTEMPTED,0)
        finally:other.rollback();other.close()


class SelectionTests(unittest.TestCase):
    def test_five_module_payload_is_pinned_bounded_and_compilable(self):
        import base64,hashlib,zlib
        from tools import knowledge_preflight_payload as payload
        encoded,checksum=payload.bundle(Path(__file__).resolve().parent.parent);raw=zlib.decompress(base64.b64decode(encoded));modules=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum);self.assertEqual([r['name'] for r in modules],[r[0] for r in payload.MODULES])
        self.assertLessEqual(len(raw),262144);self.assertLess(len(encoded)+4096,128000)
        for row in modules:
            code=base64.b64decode(row['source']);self.assertEqual(hashlib.sha256(code).hexdigest(),row['sha256']);compile(code,'<pinned-preflight-module>','exec')
    def eligible(self):
        p={'category':'automatic_retry'};s={'candidate_versions':[{'source_version_matches_current':True,'archive_metadata_recorded':True,'source_size':1024,'method_codes':['bounded_retry_preflight']}],
            'method_codes':['bounded_retry_preflight'],'current_inventory_member':True}
        return p,s,{'candidate_versions':[{'source_sha256':'a'*64,'source_archive_etag':'v1'}]}
    def test_eligibility_excludes_pause_hold_unsafe_unknown_and_incomplete_metadata(self):
        for category in ('retry_paused','governed_hold','governed_review','other_or_conflicting','no_candidate'):
            p,s,c=self.eligible();p['category']=category;self.assertNotEqual(pre.eligibility(p,s,c),'conditional_metadata_candidate_not_authorized')
        for method in pre.EXCLUDED:
            p,s,c=self.eligible();s['method_codes'].append(method);self.assertNotEqual(pre.eligibility(p,s,c),'conditional_metadata_candidate_not_authorized')
        p,s,c=self.eligible();self.assertEqual(pre.eligibility(p,s,c),'conditional_metadata_candidate_not_authorized')
        c['candidate_versions'][0]['source_sha256']='';self.assertEqual(pre.eligibility(p,s,c),'integrity_metadata_incomplete')
    def test_zero_oversize_and_multi_version_are_not_selected(self):
        for size in (0,-1,True,10485761):
            p,s,c=self.eligible();s['candidate_versions'][0]['source_size']=size;self.assertEqual(pre.eligibility(p,s,c),'size_outside_bound')
        p,s,c=self.eligible();s['candidate_versions']*=2;self.assertEqual(pre.eligibility(p,s,c),'missing_current_or_multiple_versions')


if __name__=='__main__':unittest.main()
