"""Read-only enforcement, twenty receipts, reconstruction and bounded source deltas."""
import contextlib,copy,importlib.util,io,json,os,sys,types,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
from tools import live_knowledge_inventory_reconciliation as recon
spec=importlib.util.spec_from_file_location('inventory_blocker_fixture',Path(__file__).with_name('test_knowledge_preflight_blockers.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
support=recon.support;baseline=recon.baseline

class InventoryTests(unittest.TestCase):
 connect=fixture.BlockerTests.connect
 insert=fixture.BlockerTests.insert
 save=fixture.BlockerTests.save
 def build(self):
  self.inventory={sid:{'item_id':sid,'parent_id':'PRIVATE-PARENT','area_id':'PRIVATE-AREA','name':'PRIVATE-'+sid,'metadata_json':support.canonical({'relative_path':'PRIVATE/'+sid}),**row} for sid,row in self.inventory.items()}
  return fixture.BlockerTests.build(self)
 refresh=fixture.BlockerTests.refresh
 refresh_preflight=fixture.BlockerTests.refresh_preflight
 refresh_diagnostic=fixture.BlockerTests.refresh_diagnostic
 tearDown=fixture.BlockerTests.tearDown
 def setUp(self):fixture.BlockerTests.setUp(self)
 def snapshot(self,inventory=None):
  other=self.connect()
  try:
   with contextlib.redirect_stdout(io.StringIO()):return recon.capture(recon.begin_read_only(other),inventory if inventory is not None else self.inventory,'PRIVATE-DRIVE',expected_inventory=self.header['inventory_sha256'],proof_args=self.args)
  finally:other.close()
 def frozen(self):return {t:[dict(r) for r in self.conn.execute('SELECT * FROM '+t)] for t in (*fixture.pre.TABLES,*fixture.rem.TABLES,*baseline.TABLES,*support.PLAN_TABLES,*support.SOURCE_TABLES,support.RECEIPT_TABLE)}
 def test_full_twenty_receipt_proof_and_independent_readback_without_any_writes(self):
  before=self.frozen();self.conn.commit();first=self.snapshot();second=self.snapshot();pair=recon.verify_pair(first,second)
  self.assertEqual(self.frozen(),before);self.assertEqual(first['summary']['preserved_receipt_count'],20);self.assertEqual(first['summary']['source_differences'],[]);self.assertEqual(first['summary']['critical_drift_sources'],0)
  self.assertEqual(pair['outside_approved_sources_changed'],0);self.assertEqual(first['summary']['saved_target_counts'],[0]*6);self.assertEqual(first['summary']['database_writes'],0)
 def test_baseline_reconstructs_exact_complete_snapshot(self):
  c=recon.ReadOnlyConnection(self.conn);base=recon.input_proof(c,**self.args)[0];inv,authority,selected=recon.reconstruct_baseline(c,base,self.header['inventory_sha256'])
  self.assertEqual(inv,self.inventory);self.assertEqual(set(authority),set(self.header['member_hashes'][i]['source_item_id'] for i in range(len(self.header['member_hashes']))));self.assertEqual(sum(v['category']!='legacy_available' for v in selected.values()),5)
 def test_current_added_unrepresented_identity_is_reported_not_adopted(self):
  inv=copy.deepcopy(self.inventory);inv['PRIVATE-NEW']={**inv['s1'],'item_id':'PRIVATE-NEW'};s=self.snapshot(inv)['summary'];row=s['source_differences'][0]
  self.assertEqual(s['inventory_diff']['added'],1);self.assertEqual(s['missing_representation'],1);self.assertEqual(row['relation'],'outside_approved_baseline');self.assertFalse(row['currently_represented']);self.assertFalse(s['baseline_adopted']);self.assertFalse(s['historical_failed_final_reconstructed_by_exact_hash'])
 def test_new_represented_identity_is_considered_without_expanding_approved_scope(self):
  self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER','PRIVATE-NEW','PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'));self.conn.commit()
  inv=copy.deepcopy(self.inventory);inv['PRIVATE-NEW']={**inv['s1'],'item_id':'PRIVATE-NEW'};s=self.snapshot(inv)['summary']
  self.assertTrue(s['source_differences'][0]['currently_represented']);self.assertEqual(s['approved_unresolved_sources'],5);self.assertEqual(s['unresolved_files'],6);self.assertTrue(all(q['considered_count']==s['represented_files'] for q in s['queries']))
 def test_approved_inventory_metadata_change_is_correlated(self):
  inv=copy.deepcopy(self.inventory);inv['s1']['size']+=1;s=self.snapshot(inv)['summary'];self.assertEqual(s['critical_drift_sources'],1)
  row=next(r for r in s['source_differences'] if r['difference']=='changed');self.assertEqual(row['relation'],'approved_unresolved');self.assertIn('size',row['inventory_change_groups']);self.assertIn('current_source',row['critical_fields_changed'])
 def test_missing_approved_identity_is_not_misrepresented_as_new_source(self):
  inv=copy.deepcopy(self.inventory);del inv['s1'];s=self.snapshot(inv)['summary'];self.assertEqual(s['inventory_diff']['removed'],1);self.assertEqual(s['source_differences'][0]['difference'],'removed')
 def test_independent_rights_or_version_drift_blocks_success(self):
  first=self.snapshot();self.conn.execute("UPDATE m365_knowledge_candidates SET decision='PRIVATE-RIGHTS-CHANGE' WHERE id=1");self.conn.commit();second=self.snapshot();self.assertGreater(second['summary']['critical_drift_sources'],0)
  with self.assertRaisesRegex(ValueError,'INDEPENDENT_APPROVED_SOURCE_DRIFT'):recon.verify_pair(first,second)
 def test_pause_hold_checkpoint_changes_cannot_pass_readback(self):
  first=self.snapshot();self.conn.execute("UPDATE m365_bulk_items SET attempts=attempts+1 WHERE item_id='s2'");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'PROTECTED_PAUSE_HOLD_DRIFT'):recon.verify_pair(first,self.snapshot())
 def test_observation_clocks_do_not_change_approval_or_scheduling(self):
  first=self.snapshot();self.conn.execute("UPDATE m365_knowledge_candidates SET reviewed_at='new observation'");self.conn.execute('UPDATE m365_bulk_items SET updated_at=999');self.conn.execute('UPDATE m365_bulk_extraction_checks SET checked_at=999');self.conn.commit();second=self.snapshot()
  self.assertEqual(recon.verify_pair(first,second)['outside_approved_sources_changed'],0)
 def test_twentieth_receipt_full_row_tamper_is_rejected(self):
  rid=self.review['current_consideration']['receipts'][-1]['receipt_id'];self.conn.execute('UPDATE '+support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(rid,));self.conn.commit()
  with self.assertRaisesRegex(ValueError,'PRESERVED_RECEIPT_DRIFT'):self.snapshot()
 def test_baseline_raw_payload_tamper_is_rejected(self):
  self.conn.execute('UPDATE '+baseline.TABLES[1]+" SET payload_json=payload_json || ' ' WHERE source_item_id='s1'");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'BASELINE_MEMBER_DRIFT'):self.snapshot()
 def test_saved_output_presence_is_not_silently_ignored(self):
  self.conn.execute('CREATE TABLE '+recon.FAILED_TABLES[0]+' (operation_key TEXT PRIMARY KEY)');self.conn.execute('INSERT INTO '+recon.FAILED_TABLES[0]+' VALUES(?)',(recon.FAILED_KEY,));self.conn.commit()
  with self.assertRaisesRegex(ValueError,'SAVED_OUTPUT_REQUIRES_RECONCILIATION'):self.snapshot()
 def test_no_write_escape_through_sql_or_facade(self):
  c=recon.ReadOnlyConnection(self.conn)
  for sql in ('DELETE FROM m365_bulk_items','CREATE TABLE forbidden(x TEXT)','UPDATE m365_knowledge_holds SET status=\'Released\'','SELECT 1; DELETE FROM m365_bulk_items','WITH x AS (DELETE FROM m365_bulk_items RETURNING *) SELECT * FROM x','SELECT * INTO forbidden FROM m365_bulk_items','SET TRANSACTION READ WRITE','PRAGMA query_only=OFF','SELECT 1 -- comment','SELECT 1 /* comment */'):
   with self.assertRaisesRegex(ValueError,'QUERY_DENIED'):c.execute(sql)
 def test_database_enforces_read_only_below_facade(self):
  other=self.connect()
  try:
   recon.begin_read_only(other)
   with self.assertRaises(Exception) as caught:other.execute('DELETE FROM m365_bulk_items')
   if getattr(other,'backend','sqlite')=='postgres':self.assertEqual(getattr(caught.exception,'sqlstate',''),'25006')
  finally:other.close()
 def test_emitted_source_deltas_and_summary_do_not_expose_names_paths_or_identifiers(self):
  inv=copy.deepcopy(self.inventory);inv['PRIVATE-NEW']={**inv['s1'],'item_id':'PRIVATE-NEW','name':'PRIVATE-FILE'};s=self.snapshot(inv)['summary']
  with contextlib.redirect_stdout(io.StringIO()) as out:recon.emit(s,{'outside_approved_sources_changed':0})
  self.assertNotIn('PRIVATE',out.getvalue());self.assertRegex(s['source_differences'][0]['source_id_sha256'],'^[0-9a-f]{64}$')
 def test_historical_snapshot_reconstruction_requires_complete_hash_match(self):
  self.assertFalse(self.snapshot()['summary']['historical_failed_final_reconstructed_by_exact_hash'])
  with patch.object(recon,'FAILED_FINAL_SHA',support.snapshot_digest(self.inventory)):self.assertTrue(self.snapshot()['summary']['historical_failed_final_reconstructed_by_exact_hash'])
 def test_terminal_report_requires_source_hashes_stability_and_full_controls(self):
  from tools.validate_knowledge_inventory import verify_log
  inv=copy.deepcopy(self.inventory);inv['PRIVATE-NEW']={**inv['s1'],'item_id':'PRIVATE-NEW'};summary=self.snapshot(inv)['summary'];summary.update(physical_files=23748,represented_files=23758,approved_unresolved_sources=8430,baseline_inventory_sha256=recon.BASELINE_INVENTORY_SHA)
  with contextlib.redirect_stdout(io.StringIO()) as out:recon.emit(summary,{'outside_approved_sources_changed':0,'protected_checkpoints_unchanged':1,'paused_membership_unchanged':1,'held_membership_unchanged':1})
  lines=out.getvalue().splitlines()+['STABILITY_CONSECUTIVE_COMPLETE_INVENTORIES_EQUAL=1']
  for i in (1,2,3):lines.extend(['STABILITY_SAMPLE_'+str(i)+'_COMPLETE=1','STABILITY_SAMPLE_'+str(i)+'_FILES=23748','STABILITY_SAMPLE_'+str(i)+'_SHA256='+summary['inventory_sha256']])
  lines+=['STABILITY_RECON_FINAL_'+k.upper()+'=0' for k in support.inventory_diff(inv,inv)]
  text='\n'.join('2026-11-16T18:00:00Z stdout F '+line for line in lines);verify_log(text)
  for changed in (text.replace('INVENTORY_RECON_PRESERVED_RECEIPTS=20','INVENTORY_RECON_PRESERVED_RECEIPTS=19'),text.replace('STABILITY_RECON_FINAL_ETAG=0','STABILITY_RECON_FINAL_ETAG=1'),text.replace(summary['source_differences_sha256'],'0'*64),text.replace('INVENTORY_RECON_READBACK_PROTECTED_CHECKPOINTS_UNCHANGED=1','INVENTORY_RECON_READBACK_PROTECTED_CHECKPOINTS_UNCHANGED=0')):
   with self.assertRaises(AssertionError):verify_log(changed)

@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated PostgreSQL CI only')
class PostgreSQLInventoryTests(InventoryTests):
 connect=fixture.PostgreSQLBlockerTests.connect
 def setUp(self):fixture.PostgreSQLBlockerTests.setUp(self)
 def tearDown(self):fixture.PostgreSQLBlockerTests.tearDown(self)

class InventoryPolicyTests(unittest.TestCase):
 def test_final_inventory_equality_checks_versions_not_only_counts(self):
  row={'item_id':'PRIVATE-ID','etag':'v1','size':12,'metadata_json':'{}'};old={'PRIVATE-ID':row};new={'PRIVATE-ID':{**row,'etag':'v2'}}
  with contextlib.redirect_stdout(io.StringIO()) as out:
   recon.verify_final_inventory(old,copy.deepcopy(old))
   with self.assertRaisesRegex(ValueError,'FINAL_INVENTORY_DRIFT'):recon.verify_final_inventory(old,new)
  self.assertNotIn('PRIVATE',out.getvalue());self.assertIn('STABILITY_RECON_FINAL_ETAG=1',out.getvalue())
 def test_source_delta_bound_refuses_truncation(self):
  inv={str(i):{'item_id':str(i)} for i in range(101)}
  with self.assertRaisesRegex(ValueError,'DELTA_REPORT_BOUND'):recon.source_deltas({},inv,{}, {},{},set())
 def test_frozen_proof_functions_are_copied_without_changes(self):
  import inspect
  self.assertEqual(inspect.getsource(recon.input_proof),inspect.getsource(fixture.diag.input_proof))
  self.assertEqual(inspect.getsource(recon.remediation_proof),inspect.getsource(fixture.diag.remediation_proof))
 def test_task_queries_are_isolated_from_frozen_module(self):
  self.assertEqual(recon.search_matrix.__globals__['QUERIES'],recon.QUERIES);self.assertNotEqual(recon.QUERIES,recon.rem.QUERIES)
 def test_payload_stays_in_original_envelope(self):
  import base64,zlib,hashlib
  from tools.knowledge_inventory_payload import bundle,MODULES
  encoded,checksum=bundle(Path(__file__).resolve().parent.parent);raw=zlib.decompress(base64.b64decode(encoded));self.assertLessEqual(len(raw),262144);self.assertLess(len(encoded)+4096,128000);self.assertEqual(hashlib.sha256(raw).hexdigest(),checksum)
  rows=json.loads(raw);self.assertEqual([r['name'] for r in rows],[r[0] for r in MODULES])
  for row in rows:compile(base64.b64decode(row['source']),'<pinned-inventory>','exec')

if __name__=='__main__':unittest.main()
