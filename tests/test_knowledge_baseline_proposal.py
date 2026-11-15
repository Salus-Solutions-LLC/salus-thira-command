"""Exact source membership, atomic new coverage, original receipts and approval boundary."""
import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from tools import live_knowledge_baseline_proposal as baseline
from salcapa_knowledge_consideration import consider

spec=importlib.util.spec_from_file_location('baseline_fixture',Path(__file__).with_name('test_knowledge_postsearch_resume.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class BaselineTests(unittest.TestCase):
    connect=fixture.ContinuationTests.connect
    insert=fixture.ContinuationTests.insert
    setUp=fixture.ContinuationTests.setUp
    tearDown=fixture.ContinuationTests.tearDown

    def build(self):
        conn=baseline.ProposalConnection(self.conn)
        evidence=baseline.support.read_evidence(conn)
        matrix=baseline.search_matrix(conn)
        core=baseline.core_snapshot(conn)
        self.conn.commit()
        header,members=baseline.build_proposal(evidence,self.inventory,matrix,core,'PRIVATE-DRIVE',expected=fixture.prior.COHORTS,expected_exceptions=1)
        return header,members,core

    def save(self,header,members,core,**kwargs):
        with contextlib.redirect_stdout(io.StringIO()):baseline.commit_proposal(self.conn,header,members,core,**kwargs)

    def refresh_fixture(self):
        header,members,core=self.build()
        conn=baseline.ProposalConnection(self.conn)
        context={'evidence':baseline.support.read_evidence(conn),
                 'families':{family:baseline.search_matrix(conn,family=family) for family in ('C','B','H')},
                 'inventory':self.inventory,'drive_id':'PRIVATE-DRIVE',
                 'expected':fixture.prior.COHORTS,'expected_exceptions':1}
        self.conn.commit()
        return header,members,core,context

    def refreshed_save(self,prepared):
        header,members,core,context=prepared
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=baseline.commit_proposal(self.conn,header,members,core,refresh=context)
        return result,out.getvalue()

    def test_family_flags_exactly_recombine_full_search_and_scoped_candidate_projection(self):
        _,_,_,context=self.refresh_fixture()
        conn=baseline.ProposalConnection(self.conn)
        self.assertEqual(baseline.combine_families(context['families']),baseline.search_matrix(conn))
        self.assertEqual(baseline.search_matrix(conn,family='C',source_ids={'s5'}),{'s5':context['families']['C']['s5']})
        self.assertEqual(baseline.candidate_subset(conn,{'s1','s5'}),[r for r in context['evidence']['candidates'] if r['source_item_id'] in {'s1','s5'}])

    def test_current_bulk_metadata_refresh_updates_every_flag_without_touching_sources(self):
        prepared=self.refresh_fixture()
        self.conn.execute('UPDATE m365_bulk_items SET metadata_json=?,status=?,reason=?',(json.dumps({'current':'baseline metadata rights audit'}),'Retry','verification'))
        self.conn.commit()
        (header,members,current),logs=self.refreshed_save(prepared)
        self.assertEqual(header['locked_refresh']['delta']['bulk']['changed'],6)
        self.assertEqual(header['locked_refresh']['candidate_sources_refreshed'],0)
        self.assertIn('BASELINE_DRIFT_BULK_FIELD_METADATA_SHA256=6',logs)
        self.assertNotIn('PRIVATE',logs)
        expected=baseline.search_matrix(baseline.ProposalConnection(self.conn))
        for member in members:
            self.assertEqual(member['matched_queries'],[label for i,(label,_) in enumerate(baseline.QUERIES) if expected[member['source_item_id']][i]])
        self.assertTrue(all(r['status']=='Retry' for r in current['bulk']))

    def test_changed_classification_is_parsed_and_researched_under_lock(self):
        prepared=self.refresh_fixture()
        obj={'extraction':{'status':'Automatic Retry Required','text':'','failure_code':'PDF_ENCRYPTED'},'note':'current baseline verification rights'}
        self.conn.execute('UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=3',(json.dumps(obj),));self.conn.commit()
        (header,members,_),_=self.refreshed_save(prepared)
        self.assertEqual(header['locked_refresh']['candidate_sources_refreshed'],1)
        row=next(m for m in members if m['source_item_id']=='s3')['candidate_versions'][0]
        self.assertEqual(row['failure_code'],'PDF_ENCRYPTED')
        self.assertEqual(header['categories'],fixture.prior.COHORTS)
        self.assertEqual(header['search_matrix_sha256'],baseline.support.digest(baseline.search_matrix(baseline.ProposalConnection(self.conn))))
        with contextlib.redirect_stdout(io.StringIO()):baseline.verify_saved(baseline.ProposalConnection(self.conn),header,members)

    def test_current_hold_and_review_dispositions_are_retained_without_approval_authority(self):
        prepared=self.refresh_fixture()
        self.conn.execute("UPDATE m365_knowledge_holds SET hold_reason='rights unsafe baseline',reviewed_by='PRIVATE-REVIEWER'")
        self.conn.execute("UPDATE m365_knowledge_candidates SET decision='Approved',reviewed_by='PRIVATE-REVIEWER' WHERE id=1")
        self.conn.commit()
        (header,members,_),logs=self.refreshed_save(prepared)
        held=next(m for m in members if m['source_item_id']=='s4')
        self.assertEqual(held['holds'][0]['hold_reason'],'rights unsafe baseline')
        self.assertEqual(held['category'],'governed_hold')
        self.assertFalse(header['baseline_accepted']);self.assertFalse(held['processing_authorized'])
        self.assertEqual(header['search_matrix_sha256'],baseline.support.digest(baseline.search_matrix(baseline.ProposalConnection(self.conn))))
        self.assertNotIn('PRIVATE',logs)

    def test_equal_totals_cannot_hide_swapped_source_category_membership(self):
        prepared=self.refresh_fixture()
        for number,status in ((1,'Retry Paused'),(2,'Review Required')):
            self.conn.execute('UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=?',(json.dumps({'extraction':{'status':status,'text':'','failure_code':'PDF_ENCRYPTED'}}),number))
        self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_COHORT_MEMBERSHIP_DRIFT'):self.refreshed_save(prepared)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)

    def test_refresh_rejects_identity_version_membership_and_wrong_cohort(self):
        prepared=self.refresh_fixture()
        self.conn.execute("UPDATE m365_bulk_items SET etag='v2' WHERE item_id='s1'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_IDENTITY_VERSION_DRIFT'):self.refreshed_save(prepared)
        self.conn.execute("UPDATE m365_bulk_items SET etag='v1' WHERE item_id='s1'")
        self.conn.execute('UPDATE m365_knowledge_candidates SET classification_json=? WHERE id=3',(json.dumps({'extraction':{'status':'Complete','text':'new content'}}),));self.conn.commit()
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_SCOPE_DRIFT'):self.refreshed_save(prepared)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)
        self.assertEqual(baseline.COMMIT_ATTEMPTED,0)

    def test_excess_candidate_refresh_is_rejected_before_any_new_receipt(self):
        prepared=self.refresh_fixture()
        self.conn.execute("UPDATE m365_knowledge_candidates SET classification_json=classification_json || ' ' WHERE id IN (1,2)")
        self.conn.commit()
        with patch.object(baseline,'MAX_REFRESH_SOURCES',1):
            with self.assertRaisesRegex(ValueError,'REFRESH_SCOPE_EXCEEDED'):self.refreshed_save(prepared)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)

    def test_refresh_independent_payloads_receipts_and_current_core_match(self):
        prepared=self.refresh_fixture()
        self.conn.execute("UPDATE m365_bulk_items SET reason='current metadata' WHERE item_id='s1'");self.conn.commit()
        (header,members,current),_=self.refreshed_save(prepared)
        other=self.connect()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                conn=baseline.begin_read_only(other);baseline.verify_saved(conn,header,members)
                self.assertEqual(baseline.core_snapshot(conn),current)
            self.assertEqual(header['execution_phase_key'],baseline.PHASE_KEY)
        finally:other.close()

    def test_source_partition_covers_all_versions_current_members_and_separate_exception(self):
        header,members,_=self.build()
        self.assertEqual(header['represented_files'],6)
        self.assertEqual(header['unresolved_files'],5)
        self.assertEqual(header['categories'],fixture.prior.COHORTS)
        self.assertEqual(len(members),6)
        self.assertEqual(len(next(m for m in members if m['source_item_id']=='s5')['candidate_versions']),2)
        self.assertTrue(next(m for m in members if m['source_item_id']=='s6')['availability_exception'])
        self.assertFalse(header['baseline_accepted'])
        self.assertFalse(header['historical_membership_reconstructed'])
        self.assertTrue(all(not m['processing_authorized'] and not m['content_reviewed_or_qualified_by_task'] for m in members))

    def test_two_no_candidate_sources_and_historical_representation_remain_explicit(self):
        for source in ('s7','s8'):
            self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER',source,'PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'))
        self.inventory['s7']=dict(self.inventory['s1'])
        self.conn.commit()
        conn=baseline.ProposalConnection(self.conn)
        evidence=baseline.support.read_evidence(conn);matrix=baseline.search_matrix(conn);core=baseline.core_snapshot(conn)
        expected=dict(fixture.prior.COHORTS);expected['no_candidate']=2
        header,members=baseline.build_proposal(evidence,self.inventory,matrix,core,'PRIVATE-DRIVE',expected=expected,expected_exceptions=1)
        self.assertEqual(header['represented_not_in_current_inventory'],1)
        self.assertEqual(header['categories']['no_candidate'],2)
        self.assertFalse(next(m for m in members if m['source_item_id']=='s8')['current_inventory_member'])
        self.assertEqual(next(m for m in members if m['source_item_id']=='s7')['candidate_versions'],[])

    def test_bulk_insert_boundaries_preserve_every_member_and_exact_payload(self):
        for number in range(7,212):
            self.insert(number,'extra-'+str(number),{'extraction':{'status':'Complete','text':'source baseline'}})
        self.conn.commit()
        header,members,core=self.build()
        self.save(header,members,core)
        self.assertEqual(len(members),211)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+baseline.TABLES[1]).fetchone()[0],211)
        with contextlib.redirect_stdout(io.StringIO()):baseline.verify_saved(baseline.ProposalConnection(self.conn),header,members)

    def test_search_matrix_matches_deployed_consider_semantics_for_every_query(self):
        self.conn.execute("UPDATE m365_knowledge_candidates SET source_name='MiXeD BASELINE' WHERE id=1")
        self.conn.execute("UPDATE m365_bulk_items SET metadata_json=? WHERE item_id='s3'",(json.dumps({'note':'SUPPORTIVE metadata rights unsafe'}),))
        self.conn.execute("UPDATE m365_knowledge_holds SET source_relative_path='audit verification'")
        self.conn.execute("UPDATE m365_bulk_items SET status='Removed',name='qualifying baseline' WHERE item_id='s5'")
        self.conn.execute('UPDATE m365_knowledge_candidates SET source_name=NULL WHERE id=4')
        self.conn.execute("UPDATE m365_bulk_items SET reason=NULL WHERE item_id='s2'")
        self.conn.commit()
        header,_,_=self.build()
        self.assertTrue(all(0<row['matched_count']<6 for row in header['new_receipts']))
        for receipt,(_,query) in zip(header['new_receipts'],baseline.QUERIES):
            with patch.dict(os.environ,{'SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES':'6'}):
                result=consider(self.conn,query,'fictional comparison',header['created_at'])
            self.assertEqual(receipt['matched_count'],result['coverage']['matched_files'])
            self.assertEqual(receipt['considered_count'],result['coverage']['considered_files'])
            self.assertEqual(receipt['content_available_count'],result['coverage']['content_available_files'])

    def test_atomic_save_independent_exact_readback_and_no_original_receipt_changes(self):
        header,members,core=self.build()
        self.save(header,members,core)
        other=self.connect()
        try:
            with contextlib.redirect_stdout(io.StringIO()):baseline.verify_saved(baseline.begin_read_only(other),header,members)
            self.assertEqual(baseline.COMMIT_ACKNOWLEDGED,1)
        finally:other.close()
        self.assertEqual([dict(r) for r in self.conn.execute('SELECT * FROM m365_knowledge_consideration_receipts WHERE actor LIKE ? ORDER BY actor',('System Administrator - task consideration salus-availability-recovery-plan-20261115 / %',)).fetchall()],self.receipts_before)

    def test_rollback_couples_all_new_receipts_and_members_without_partial_coverage(self):
        header,members,core=self.build()
        with self.assertRaisesRegex(ValueError,'INJECTED_ROLLBACK'):self.save(header,members,core,fail_after_members=True)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)
        with contextlib.redirect_stdout(io.StringIO()):baseline.empty_target(baseline.ProposalConnection(self.conn))

    def test_repeat_proposal_does_not_duplicate_receipts_or_replace_evidence(self):
        header,members,core=self.build();self.save(header,members,core)
        with self.assertRaisesRegex(ValueError,'PROPOSAL_ALREADY_PRESENT'):self.save(header,members,core)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],8)

    def test_names_metadata_classification_rights_and_membership_drift_each_block_commit(self):
        _,_,before=self.build()
        cases=(('UPDATE m365_knowledge_candidates SET source_name=? WHERE id=1','PRIVATE-CHANGED',"UPDATE m365_knowledge_candidates SET source_name='Fictional' WHERE id=1"),
               ('UPDATE m365_bulk_items SET metadata_json=? WHERE item_id=\'s1\'','{"new":"baseline"}',"UPDATE m365_bulk_items SET metadata_json='{}' WHERE item_id='s1'"),
               ('UPDATE m365_knowledge_holds SET hold_reason=?','PRIVATE-CHANGE',"UPDATE m365_knowledge_holds SET hold_reason='PRIVATE-REASON'"),
               ('UPDATE m365_knowledge_candidates SET source_etag=? WHERE id=1','v2',"UPDATE m365_knowledge_candidates SET source_etag='v1' WHERE id=1"))
        header,members,_=self.build()
        for sql,value,restore in cases:
            self.conn.execute(sql,(value,));self.conn.commit()
            with self.assertRaisesRegex(ValueError,'SOURCE_OR_SEARCH_INPUT_DRIFT'):self.save(header,members,before)
            self.conn.execute(restore);self.conn.commit()

    def test_removed_bulk_search_input_is_bound_even_when_candidate_represents_source(self):
        self.conn.execute("UPDATE m365_bulk_items SET status='Removed' WHERE item_id='s1'");self.conn.commit()
        header,members,core=self.build()
        self.conn.execute("UPDATE m365_bulk_items SET name='changed recovery' WHERE item_id='s1'");self.conn.commit()
        with self.assertRaisesRegex(ValueError,'SOURCE_OR_SEARCH_INPUT_DRIFT'):self.save(header,members,core)

    def test_checkpoint_scheduling_movement_is_not_an_authority_or_membership_change(self):
        header,members,core=self.build()
        self.conn.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1')
        self.conn.execute('UPDATE m365_bulk_items SET attempts=attempts+1,next_attempt=next_attempt+1')
        self.conn.commit()
        self.save(header,members,core)

    def test_original_receipt_change_blocks_every_new_write(self):
        header,members,core=self.build()
        self.conn.execute('UPDATE m365_knowledge_consideration_receipts SET matched_count=0');self.conn.commit()
        with self.assertRaises(baseline.support.CensusFailure):self.save(header,members,core)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM m365_knowledge_consideration_receipts').fetchone()[0],4)

    def test_different_unresolved_cohort_and_cross_drive_membership_are_rejected(self):
        conn=baseline.ProposalConnection(self.conn)
        evidence=baseline.support.read_evidence(conn);matrix=baseline.search_matrix(conn);core=baseline.core_snapshot(conn)
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_SCOPE_DRIFT'):baseline.build_proposal(evidence,self.inventory,matrix,core,'PRIVATE-DRIVE',expected_exceptions=1)
        with self.assertRaisesRegex(ValueError,'DRIVE_SCOPE_DRIFT'):baseline.build_proposal(evidence,self.inventory,matrix,core,'OTHER-DRIVE',expected=fixture.prior.COHORTS,expected_exceptions=1)

    def test_missing_coverage_and_unrepresented_current_source_are_rejected(self):
        conn=baseline.ProposalConnection(self.conn)
        evidence=baseline.support.read_evidence(conn);matrix=baseline.search_matrix(conn);core=baseline.core_snapshot(conn)
        matrix.pop('s1')
        with self.assertRaisesRegex(ValueError,'MEMBERSHIP_INVALID'):baseline.build_proposal(evidence,self.inventory,matrix,core,'PRIVATE-DRIVE',expected=fixture.prior.COHORTS,expected_exceptions=1)

    def test_mutating_cte_source_and_receipt_updates_schema_and_multiple_statements_denied(self):
        conn=baseline.ProposalConnection(self.conn);conn.writes_enabled=True
        for sql in ('UPDATE m365_knowledge_candidates SET status=\'bad\'', 'DELETE FROM m365_knowledge_consideration_receipts',
                    'CREATE TABLE secret_copy(a TEXT)', 'WITH x AS (DELETE FROM m365_knowledge_holds RETURNING *) SELECT * FROM x',
                    'SELECT 1; DELETE FROM m365_bulk_items', 'INSERT INTO m365_bulk_items VALUES(?)'):
            with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):conn.execute(sql)

    def test_exact_member_and_new_receipt_readback_rejects_tampering(self):
        header,members,core=self.build();self.save(header,members,core)
        self.conn.execute('UPDATE '+baseline.TABLES[1]+' SET category=? WHERE source_item_id=?',('bad','s1'));self.conn.commit()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError,'MEMBER_READBACK'):baseline.verify_saved(baseline.ProposalConnection(self.conn),header,members)

    def test_transaction_deadline_rolls_back_without_commit(self):
        header,members,core=self.build();ticks=iter((0,0,61))
        with self.assertRaisesRegex(ValueError,'TRANSACTION_BUDGET'):self.save(header,members,core,clock=lambda:next(ticks))
        self.assertEqual(baseline.COMMIT_ATTEMPTED,0)

    def test_lost_commit_acknowledgement_is_reported_as_ambiguous_not_zero_writes(self):
        header,members,core=self.build()
        class Lost:
            backend=getattr(self.conn,'backend','sqlite')
            def __init__(self,inner):self.inner=inner
            def execute(self,*args):return self.inner.execute(*args)
            def commit(self):self.inner.commit();raise ConnectionError('PRIVATE')
            def rollback(self):self.inner.rollback()
        with contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(ConnectionError):baseline.commit_proposal(Lost(self.conn),header,members,core)
        self.assertEqual((baseline.COMMIT_ATTEMPTED,baseline.COMMIT_ACKNOWLEDGED),(1,0))
        other=self.connect()
        try:self.assertEqual(other.execute('SELECT COUNT(*) FROM '+baseline.TABLES[0]).fetchone()[0],1)
        finally:other.close()


@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated real PostgreSQL CI only')
class PostgreSQLBaselineTests(BaselineTests):
    connect=fixture.PostgreSQLContinuationTests.connect
    def setUp(self):
        assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        c=self.connect()
        for table in (*baseline.TABLES,*baseline.support.PLAN_TABLES,*baseline.support.SOURCE_TABLES,baseline.support.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+table)
        c.commit();c.close();BaselineTests.setUp(self)
    def tearDown(self):
        self.conn.rollback()
        for table in (*baseline.TABLES,*baseline.support.PLAN_TABLES,*baseline.support.SOURCE_TABLES,baseline.support.RECEIPT_TABLE):self.conn.execute('DROP TABLE IF EXISTS '+table)
        self.conn.commit();self.conn.close();self.folder.cleanup()
    def test_existing_writer_stops_nowait_before_new_receipts(self):
        header,members,core=self.build();other=self.connect()
        try:
            other.execute("UPDATE m365_bulk_items SET status='Pending' WHERE item_id='s1'")
            with self.assertRaises(Exception) as caught:self.save(header,members,core)
            self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03')
            self.assertEqual(baseline.COMMIT_ATTEMPTED,0)
        finally:other.rollback();other.close()


if __name__=='__main__':unittest.main()
