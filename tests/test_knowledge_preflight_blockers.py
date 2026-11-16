"""Twenty-receipt proof, overlapping blockers and explicitly unapproved methods."""
import contextlib,copy,importlib.util,io,json,os
from pathlib import Path
import unittest
from tools import live_knowledge_preflight_blockers as diag
from tools import live_knowledge_preflight_proposals as pre
spec=importlib.util.spec_from_file_location('blocker_preflight_fixture',Path(__file__).with_name('test_knowledge_preflight_proposals.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
rem=diag.rem;planning=diag.planning;baseline=diag.baseline;support=diag.support

class BlockerTests(unittest.TestCase):
 connect=fixture.PreflightTests.connect
 insert=fixture.PreflightTests.insert
 save=fixture.PreflightTests.save
 tearDown=fixture.PreflightTests.tearDown
 refresh=fixture.PreflightTests.refresh
 refresh_preflight=fixture.PreflightTests.refresh_preflight
 def build(self):
  self.conn.execute("UPDATE m365_knowledge_candidates SET source_sha256='',source_archive_etag='archive-v1',source_archive_item_id='PRIVATE-ARCHIVE-' || source_item_id");self.conn.commit()
  return fixture.fixture.RemediationTests.build(self)
 def setUp(self):
  fixture.PreflightTests.setUp(self)
  with contextlib.redirect_stdout(io.StringIO()):self.review,self.reviewed,self.prior_selected,_=pre.prepare(self.conn,self.pre_context,**self.proof_args)
  self.assertEqual(self.prior_selected,[])
  self.args={**self.proof_args,'expected_review':support.digest(self.review)}
  self.refresh_diagnostic()
 def refresh_diagnostic(self):
  conn=diag.Connection(self.conn);core=baseline.core_snapshot(conn);evidence=support.read_evidence(conn);families={f:diag.search_matrix(conn,family=f) for f in ('C','B','H')}
  base,parent,remh,review,_=diag.input_proof(conn,**self.args)
  diagnostics,proposals,scope,summary=diag.diagnose_all(conn,base,parent,remh,review,evidence,core,self.inventory,expected_sources=5)
  self.context={'preview_core':core,'evidence':evidence,'families':families,'inventory':self.inventory,'drive_id':'PRIVATE-DRIVE','diagnostics':diagnostics,'proposals':proposals,'scope':scope,'summary':summary};self.conn.commit()
 def prepare(self,**kwargs):
  with contextlib.redirect_stdout(io.StringIO()) as out:result=diag.prepare(self.conn,self.context,**self.args,**kwargs)
  self.assertNotIn('PRIVATE',out.getvalue());return result
 def frozen(self):return {t:[dict(r) for r in self.conn.execute('SELECT * FROM '+t)] for t in (*pre.TABLES,*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES)}
 def test_all_sources_twenty_preserved_twentyfour_readback_and_no_promotion(self):
  before=self.frozen();receipts=[dict(r) for r in self.conn.execute('SELECT * FROM '+support.RECEIPT_TABLE)];self.conn.commit()
  h,d,p,current=self.prepare();self.assertEqual(self.frozen(),before);self.assertEqual(h['diagnosed_sources'],5);self.assertEqual(h['diagnosed_batches'],5)
  self.assertGreater(len(p),0);self.assertEqual(h['summary']['strict_existing_policy_eligible_sources'],0)
  self.assertTrue(all(s['resolution_method']=='initial_current_pair_hash_establishment' and not s['strict_existing_policy_eligible'] and not s['method_approved'] for b in p for s in b['source_bindings']))
  other=self.connect()
  try:
   conn=baseline.begin_read_only(other);self.assertEqual(diag.verify_output(conn,h,d,p),support.digest(h));self.assertEqual(diag.input_proof(conn,**self.args)[4],h['preserved_receipts_sha256'])
   now=[dict(r) for r in conn.execute('SELECT * FROM '+support.RECEIPT_TABLE)];self.assertEqual(len(now),24);self.assertTrue(all(r in now for r in receipts));self.assertEqual(baseline.core_snapshot(conn),current)
  finally:other.close()
 def test_first_reasons_reconcile_to_frozen_review_and_overlaps_do_not_sum(self):
  h,d,_,_=self.prepare();s=h['summary'];self.assertEqual(s['first_blocker_counts_exclusive'],self.review['review_dispositions']);self.assertEqual(sum(s['first_blocker_counts_exclusive'].values()),5)
  self.assertEqual(s['all_blocker_source_counts_overlapping']['source_sha256_absent'],4);self.assertTrue(s['overlapping_gate_counts_must_not_be_summed']);self.assertGreater(sum(s['all_blocker_source_counts_overlapping'].values()),5)
 def test_prior_review_raw_header_integrity(self):
  self.conn.execute('UPDATE '+pre.TABLES[0]+" SET payload_json=payload_json || ' '");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'REVIEW_HEADER_DRIFT'):self.prepare()
 def test_prior_review_batch_integrity(self):
  self.conn.execute('UPDATE '+pre.TABLES[1]+" SET payload_json=payload_json || ' '");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'REVIEW_BATCH_DRIFT'):self.prepare()
 def test_prior_review_event_integrity(self):
  self.conn.execute('UPDATE '+pre.TABLES[3]+" SET payload_json=payload_json || ' '");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'REVIEW_EVENT_DRIFT'):self.prepare()
 def test_twentieth_receipt_is_protected(self):
  rid=self.review['current_consideration']['receipts'][-1]['receipt_id'];self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(rid,));self.conn.commit()
  with self.assertRaisesRegex(ValueError,'PRESERVED_RECEIPT_DRIFT'):self.prepare()
 def test_current_rights_change_fails_before_writes(self):
  self.conn.execute("UPDATE m365_knowledge_candidates SET decision='changed rights' WHERE id=1");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.prepare()
  self.assertEqual(diag.COMMIT_ATTEMPTED,0)
 def test_source_preview_drift_rejected(self):
  self.conn.execute("UPDATE m365_knowledge_candidates SET source_etag='changed' WHERE id=1");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'SOURCE_RIGHTS_VERSION_DRIFT'):self.refresh_diagnostic()
 def test_benign_review_clock_and_selected_checkpoint_refresh(self):
  self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='new clock' WHERE id=1");self.conn.execute('UPDATE m365_bulk_items SET attempts=9,next_attempt=333');self.conn.commit()
  h,_,p,_=self.prepare();self.assertTrue(h['paused_retries_preserved']);self.assertTrue(all(r['attempts']==9 for b in p for s in b['source_bindings'] for r in s['current_bulk_checkpoints']))
 def test_all_current_query_masks_and_outside_sources_are_explicit(self):
  self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER','outside','PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'));self.inventory['outside']=dict(self.inventory['s1']);self.conn.commit();self.refresh_diagnostic()
  h,_,_,_=self.prepare();obs=h['current_consideration'];self.assertEqual(obs['unresolved_outside_diagnostic_scope'],['outside'])
  for bit,r in enumerate(obs['receipts']):self.assertEqual(sum(bool(v&(1<<bit)) for _,v in obs['per_source_coverage']),r['matched_count'])
 def test_atomic_rollback_keeps_twenty_and_empty_target(self):
  with self.assertRaisesRegex(ValueError,'INJECTED_ROLLBACK'):self.prepare(fail_after_diagnostics=True)
  self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+support.RECEIPT_TABLE).fetchone()[0],20)
  with contextlib.redirect_stdout(io.StringIO()):diag.target_empty(diag.Connection(self.conn))
 def test_duplicate_is_rejected(self):
  self.prepare()
  with self.assertRaisesRegex(ValueError,'TARGET_NOT_EMPTY'):self.prepare()
 def test_deadline_stops_before_writes(self):
  calls=0
  def clock():
   nonlocal calls
   calls+=1;return 0 if calls==1 else 61
  with self.assertRaisesRegex(ValueError,'TRANSACTION_BUDGET'):self.prepare(clock=clock)
  self.assertEqual(diag.COMMIT_ATTEMPTED,0)
 def test_lost_commit_ack_is_not_replayed(self):
  class Lost:
   backend=getattr(self.conn,'backend','sqlite')
   def execute(obj,*a):return self.conn.execute(*a)
   def commit(obj):self.conn.commit();raise ConnectionError('PRIVATE')
   def rollback(obj):self.conn.rollback()
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaises(ConnectionError):diag.prepare(Lost(),self.context,**self.args)
  self.assertEqual((diag.COMMIT_ATTEMPTED,diag.COMMIT_ACKNOWLEDGED),(1,0));self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM '+diag.TABLES[0]).fetchone()[0],1)
 def test_policy_or_method_cannot_be_self_approved(self):
  self.context['proposals'][0]['method_approved']=True
  with self.assertRaisesRegex(ValueError,'PROPOSAL_AUTHORITY_DRIFT'):self.prepare()
 def test_summary_is_recomputed_before_writes(self):
  self.context['summary']['all_blocker_source_counts_overlapping']['source_sha256_absent']=999
  with self.assertRaisesRegex(ValueError,'DIAGNOSTIC_SUMMARY_DRIFT'):self.prepare()
  self.assertEqual(diag.COMMIT_ATTEMPTED,0)
 def test_outside_source_cannot_be_selected(self):
  self.context['proposals'][0]['source_bindings'][0]['source_item_id']='outside'
  with self.assertRaisesRegex(ValueError,'PROPOSAL_SCOPE_DRIFT'):self.prepare()
 def test_bounds_cannot_be_enlarged(self):
  self.context['proposals'][0]['bounds']={**diag.BOUNDS,'maximum_selected_sources':100}
  with self.assertRaisesRegex(ValueError,'PROPOSAL_BOUND_DRIFT'):self.prepare()
 def test_readback_tamper_is_rejected(self):
  h,d,p,_=self.prepare();self.conn.execute('UPDATE '+diag.TABLES[1]+" SET payload_json=payload_json || ' '");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'OUTPUT_BATCH_DRIFT'):diag.verify_output(diag.Connection(self.conn),h,d,p)
 def test_facade_denies_input_source_receipt_or_arbitrary_writes(self):
  conn=diag.Connection(self.conn);conn.writes_enabled=True
  for sql,args in [('DELETE FROM '+pre.TABLES[0],()),('INSERT INTO '+pre.TABLES[3]+' VALUES(?,?,?)',('x',)*3),('UPDATE m365_knowledge_holds SET status=\'Released\'',()),('INSERT INTO '+support.RECEIPT_TABLE+' VALUES(?,?,?,?,?,?,?,?,?,?)',('x',)*10),('CREATE TABLE arbitrary(a TEXT)',()),('SELECT 1; DELETE FROM m365_bulk_items',()),('WITH x AS (DELETE FROM m365_knowledge_candidates RETURNING *) SELECT * FROM x',())]:
   with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):conn.execute(sql,args)

@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated PostgreSQL CI only')
class PostgreSQLBlockerTests(BlockerTests):
 connect=fixture.PostgreSQLPreflightTests.connect
 def setUp(self):
  assert os.getenv('SALUS_DATABASE_URL','').startswith('postgresql://postgres:postgres@localhost:5432/postsearch_plan') # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
  c=self.connect()
  for t in (*diag.TABLES,*pre.TABLES,*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):c.execute('DROP TABLE IF EXISTS '+t)
  c.commit();c.close();BlockerTests.setUp(self)
 def tearDown(self):
  self.conn.rollback()
  for t in (*diag.TABLES,*pre.TABLES,*rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE):self.conn.execute('DROP TABLE IF EXISTS '+t)
  self.conn.commit();self.conn.close();self.folder.cleanup()
 def test_real_checkpoint_writer_causes_nowait_failure(self):
  other=self.connect()
  try:
   other.execute('UPDATE m365_bulk_extraction_checks SET attempts=attempts+1')
   with self.assertRaises(Exception) as caught:self.prepare()
   self.assertEqual(getattr(caught.exception,'sqlstate',''),'55P03');self.assertEqual(diag.COMMIT_ATTEMPTED,0)
  finally:other.rollback();other.close()

class PolicyTests(unittest.TestCase):
 def test_task_projection_does_not_change_frozen_module_configuration(self):
  self.assertEqual(diag.search_matrix.__globals__['QUERIES'],diag.QUERIES)
  self.assertEqual(diag.observe.__globals__['ACTOR'],diag.ACTOR)
  self.assertNotEqual(rem.ACTOR,diag.ACTOR)
  self.assertNotEqual(rem.QUERIES,diag.QUERIES)
  self.assertEqual(diag.search_matrix.__code__,rem.search_matrix.__code__)
  self.assertEqual(diag.search_matrix.__kwdefaults__,rem.search_matrix.__kwdefaults__)
 def test_legacy_function_is_semantically_unchanged(self):
  import inspect
  self.assertEqual(inspect.getsource(diag.legacy_reason).replace('legacy_reason','eligibility'),inspect.getsource(pre.eligibility))
 def test_no_hard_block_is_converted_into_eligibility(self):
  self.assertEqual(diag.proposed_method(['source_sha256_absent'],'integrity_metadata_incomplete'),'initial_current_pair_hash_establishment')
  self.assertEqual(diag.proposed_method(['archive_etag_absent','source_sha256_absent'],'integrity_metadata_incomplete'),'metadata_identity_reconciliation')
  for code in set(diag.CODES)-diag.SOFT:self.assertIsNone(diag.proposed_method(sorted([code,'source_sha256_absent']),'integrity_metadata_incomplete'))
 def test_pinned_payload_retains_limits(self):
  import base64,hashlib,zlib
  from tools import knowledge_blocker_payload as payload
  encoded,checksum=payload.bundle(Path(__file__).resolve().parent.parent);raw=zlib.decompress(base64.b64decode(encoded));rows=json.loads(raw)
  self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum);self.assertEqual([r['name'] for r in rows],[r[0] for r in payload.MODULES]);self.assertLessEqual(len(raw),262144);self.assertLess(len(encoded)+4096,128000)
  for row in rows:
   code=base64.b64decode(row['source']);self.assertEqual(hashlib.sha256(code).hexdigest(),row['sha256']);compile(code,'<blocker-module>','exec')

if __name__=='__main__':unittest.main()
