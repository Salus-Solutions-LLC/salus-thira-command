"""Immutable parent/twelve receipts, source-specific proposals and no action authority."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from tools import live_knowledge_remediation_proposals as rem
spec=importlib.util.spec_from_file_location('remediation_parent_fixture',Path(__file__).with_name('test_knowledge_streamed_recovery_plan.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
planning=rem.planning;baseline=rem.baseline;support=rem.support


class RemediationTests(unittest.TestCase):
    connect=fixture.PlanningTests.connect
    insert=fixture.PlanningTests.insert
    build=fixture.PlanningTests.build
    save=fixture.PlanningTests.save
    tearDown=fixture.PlanningTests.tearDown

    def setUp(self):
        fixture.PlanningTests.setUp(self)
        fixture.PlanningTests.prepare(self)
        row=self.conn.execute('SELECT * FROM '+support.PLAN_TABLES[0]).fetchone()
        self.parent=json.loads(row['payload_json']);self.parent_sha=row['manifest_sha256']
        self.args={'expected_parent':self.parent_sha,'expected_baseline':self.manifest,'expected_batches':len(self.parent['batch_hashes']),'expected_sources':5}
        self.refresh()

    def refresh(self):
        conn=rem.Connection(self.conn)
        core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn)
        families={f:rem.search_matrix(conn,family=f) for f in ('C','B','H')}
        proposals,scope=rem.build_proposals(conn,self.header,self.parent,evidence,core,self.inventory,expected_sources=5)
        self.context={'preview_core':core,'evidence':evidence,'families':families,'inventory':self.inventory,'drive_id':'PRIVATE-DRIVE','proposals':proposals,'scope':scope}
        self.conn.commit()

    def prepare(self,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()) as logs:
            result=rem.prepare(self.conn,self.context,**self.args,**kwargs)
        self.assertNotIn('PRIVATE',logs.getvalue())
        return result

    def parent_proof(self,conn=None):
        return rem.parent_proof(conn or rem.Connection(self.conn),expected=self.parent_sha,baseline_sha=self.manifest,expected_batches=len(self.parent['batch_hashes']),expected_sources=5)

    def frozen(self):
        return {t:[dict(r) for r in self.conn.execute('SELECT * FROM '+t).fetchall()] for t in (*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES)}

    def test_exact_parent_baseline_twelve_receipts_and_all_outputs_on_independent_connection(self):
        frozen=self.frozen();old=[dict(r) for r in self.conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor')];self.conn.commit()
        header,proposals,core=self.prepare()
        self.assertEqual(self.frozen(),frozen)
        self.assertEqual(header['proposal_count'],5);self.assertEqual(header['source_count'],5)
        self.assertTrue(all(not p['processing_authorized'] and not p['retry_resume_authorized'] and not p['hold_release_authorized'] for p in proposals))
        self.assertEqual({p['batch_key'] for p in proposals},{r['batch_key'] for r in self.parent['batch_hashes']})
        other=self.connect()
        try:
            conn=baseline.begin_read_only(other)
            self.assertEqual(rem.verify_output(conn,header,proposals),support.digest(header))
            self.assertEqual(self.parent_proof(conn)[2],header['preserved_receipts_sha256'])
            now=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE+' ORDER BY actor')]
            self.assertEqual(len(now),16);self.assertTrue(all(r in now for r in old))
            self.assertEqual(baseline.core_snapshot(conn),core)
        finally:other.close()

    def test_full_current_query_masks_reconcile_and_family_projection_matches(self):
        conn=rem.Connection(self.conn)
        self.assertEqual(baseline.combine_families(self.context['families']),rem.search_matrix(conn))
        self.assertEqual(rem.search_matrix(conn,family='C',source_ids={'s1'}),{'s1':self.context['families']['C']['s1']})
        self.conn.commit();header,_,_=self.prepare()
        obs=header['current_consideration'];self.assertEqual(len(obs['per_source_coverage']),6)
        for bit,row in enumerate(obs['receipts']):self.assertEqual(sum(bool(mask&(1<<bit)) for _,mask in obs['per_source_coverage']),row['matched_count'])

    def test_byte_change_in_parent_header_cannot_hide_behind_same_semantic_json(self):
        self.conn.execute('UPDATE '+support.PLAN_TABLES[0]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'PARENT_HEADER_DRIFT'):self.parent_proof()

    def test_parent_batch_payload_hash_and_event_are_verified(self):
        self.conn.execute('UPDATE '+support.PLAN_TABLES[1]+" SET payload_json=payload_json || ' ' WHERE batch_key=?",(self.parent['batch_hashes'][0]['batch_key'],));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'PARENT_BATCH_DRIFT'):self.prepare()

    def test_baseline_header_bytes_and_event_are_verified(self):
        self.conn.execute('UPDATE '+baseline.TABLES[0]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'BASELINE_HEADER_DRIFT'):self.prepare()

    def test_all_twelve_receipts_are_preserved_not_only_original_eight(self):
        receipt=self.parent['current_consideration']['receipts'][0]['receipt_id']
        self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(receipt,));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'TASK_RECEIPT_DRIFT'):self.prepare()
        self.assertEqual(rem.COMMIT_ATTEMPTED,0)

    def test_parent_rights_version_change_rejected_during_streamed_preview(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET decision='changed authority' WHERE id=1");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.refresh()

    def test_locked_scope_classification_change_is_rejected_before_writes(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET classification_json=classification_json || ' ' WHERE id=1");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.prepare()
        self.assertEqual((rem.COMMIT_ATTEMPTED,rem.COMMIT_ACKNOWLEDGED),(0,0))

    def test_locked_review_clock_and_queue_refresh_are_captured_without_mutation(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='new clock' WHERE id=1")
        self.conn.execute('UPDATE m365_bulk_items SET attempts=7,next_attempt=999');self.conn.commit()
        header,proposals,_=self.prepare()
        self.assertTrue(header['paused_retries_preserved']);self.assertTrue(header['governed_holds_preserved'])
        self.assertTrue(all(row['attempts']==7 for p in proposals for s in p['source_bindings'] for row in s['current_bulk_checkpoints']))
        self.assertTrue(all(r['attempts']==7 for r in self.conn.execute('SELECT attempts FROM m365_bulk_items')))

    def test_new_unresolved_source_is_considered_and_explicitly_outside_parent_proposals(self):
        self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER','outside-source','PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'))
        self.inventory['outside-source']=dict(self.inventory['s1']);self.conn.commit();self.refresh()
        header,proposals,_=self.prepare();obs=header['current_consideration']
        self.assertEqual(obs['represented_files'],7);self.assertEqual(obs['unresolved_outside_parent_batches'],['outside-source'])
        self.assertEqual(len(proposals),5);self.assertEqual(header['source_count'],5)

    def test_proposal_hash_binding_rejects_dropped_parent_batch(self):
        self.context['proposals'].pop()
        with self.assertRaisesRegex(ValueError,'PARENT_SCOPE_DRIFT'):self.prepare()

    def test_atomic_rollback_preserves_twelve_and_no_proposals(self):
        with self.assertRaisesRegex(ValueError,'INJECTED_ROLLBACK'):self.prepare(fail_after_batches=True)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],12)
        with contextlib.redirect_stdout(io.StringIO()):rem.target_empty(rem.Connection(self.conn))

    def test_second_preparation_is_rejected(self):
        self.prepare()
        with self.assertRaisesRegex(ValueError,'TARGET_NOT_EMPTY'):self.prepare()

    def test_transaction_deadline_stops_before_any_writes(self):
        count=0
        def clock():
            nonlocal count
            count+=1;return 0 if count==1 else 61
        with self.assertRaisesRegex(ValueError,'TRANSACTION_BUDGET'):self.prepare(clock=clock)
        self.assertEqual(rem.COMMIT_ATTEMPTED,0)

    def test_lost_commit_acknowledgement_is_ambiguous_and_output_is_durable(self):
        class Lost:
            backend=getattr(self.conn,'backend','sqlite')
            def execute(obj,*args):return self.conn.execute(*args)
            def commit(obj):self.conn.commit();raise ConnectionError('PRIVATE')
            def rollback(obj):self.conn.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConnectionError):rem.prepare(Lost(),self.context,**self.args)
        self.assertEqual((rem.COMMIT_ATTEMPTED,rem.COMMIT_ACKNOWLEDGED),(1,0))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+rem.TABLES[0]).fetchone()[0],1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],16)

    def test_sql_facade_rejects_source_parent_baseline_and_preserved_receipt_writes(self):
        conn=rem.Connection(self.conn);conn.writes_enabled=True
        for sql,params in [('DELETE FROM '+support.RECEIPT_TABLE,()),('UPDATE m365_knowledge_holds SET status=\'Released\'',()),
            ('INSERT INTO '+support.PLAN_TABLES[0]+' VALUES(?,?,?,?,?)',('x',)*5),('INSERT INTO '+baseline.TABLES[0]+' VALUES(?,?,?,?,?)',('x',)*5),
            ('INSERT INTO '+support.RECEIPT_TABLE+' VALUES(?,?,?,?,?,?,?,?,?,?)',('x',)*10),('CREATE TABLE arbitrary(a TEXT)',()),
            ('SELECT 1; DELETE FROM m365_bulk_items',()),('WITH x AS (DELETE FROM m365_knowledge_candidates RETURNING *) SELECT * FROM x',())]:
            with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):conn.execute(sql,params)

    def test_proposal_payload_tamper_is_rejected_by_independent_readback(self):
        header,proposals,_=self.prepare()
        self.conn.execute('UPDATE '+rem.TABLES[1]+" SET payload_json=payload_json || ' '");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'OUTPUT_BATCH_DRIFT'):rem.verify_output(rem.Connection(self.conn),header,proposals)


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLRemediationTests(RemediationTests):
    connect=fixture.PostgreSQLPlanningTests.connect
    def setUp(self):
        assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        c=self.connect()
        for table in (*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+table)
        c.commit();c.close();RemediationTests.setUp(self)
    def tearDown(self):
        self.conn.rollback()
        for table in (*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):self.conn.execute('DROP TABLE IF EXISTS '+table)
        self.conn.commit();self.conn.close();self.folder.cleanup()

    def test_parent_writer_or_checkpoint_writer_stops_nowait_before_writes(self):
        other=self.connect()
        try:
            other.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1')
            with self.assertRaises(Exception) as caught:self.prepare()
            self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03')
            self.assertEqual(rem.COMMIT_ATTEMPTED,0)
        finally:other.rollback();other.close()


class MethodTests(unittest.TestCase):
    def test_four_module_source_bundle_fits_single_argument_and_hashes_each_module(self):
        import base64,hashlib,zlib
        from tools import knowledge_remediation_payload as payload
        root=Path(__file__).resolve().parent.parent
        encoded,checksum=payload.bundle(root);raw=zlib.decompress(base64.b64decode(encoded));modules=json.loads(raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum)
        self.assertEqual([m['name'] for m in modules],[m[0] for m in payload.MODULES])
        for module in modules:
            code=base64.b64decode(module['source']);self.assertEqual(hashlib.sha256(code).hexdigest(),module['sha256']);compile(code,'<pinned-module>','exec')
        self.assertLess(len(encoded)+4096,128000)

    def test_hold_and_paused_categories_do_not_authorize_retry_or_release(self):
        self.assertEqual(rem.methods_for({'category':'governed_hold','failure_codes':['PDF_ACTIVE_CONTENT']}),['owner_hold_review'])
        self.assertIn('processor_remediation',rem.methods_for({'category':'retry_paused','failure_codes':['TRANSCRIPTION_FAILED']}))
        self.assertIn('bounded_retry_preflight',rem.methods_for({'category':'automatic_retry','failure_codes':['PDF_ENCRYPTED']}))

    def test_encryption_active_content_unknown_and_conflicting_version_routes_are_distinct(self):
        for code,method in [('PDF_ENCRYPTED','authorized_readable_source'),('PDF_ACTIVE_CONTENT','safe_derivative_review'),('DOCUMENT_XML_INVALID','integrity_and_repair_review'),('UNKNOWN','unknown_condition_review')]:
            self.assertIn(method,rem.methods_for({'category':'governed_review','failure_codes':[code]}))
        self.assertEqual(rem.methods_for({'category':'other_or_conflicting','failure_codes':[]}),['all_version_reconciliation'])
        self.assertEqual(rem.methods_for({'category':'no_candidate','failure_codes':[]}),['missing_candidate_provenance'])


if __name__=='__main__':unittest.main()
