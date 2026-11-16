"""Source/category binding, genuine database read-only controls, drift and privacy."""
import contextlib,copy,hashlib,importlib.util,io,os,unittest
from pathlib import Path
from tools import live_knowledge_outside_cohort as outside
spec=importlib.util.spec_from_file_location('outside_inventory_fixture',Path(__file__).with_name('test_knowledge_inventory_reconciliation.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class OutsideTests(unittest.TestCase):
 connect=fixture.InventoryTests.connect
 insert=fixture.InventoryTests.insert
 save=fixture.InventoryTests.save
 build=fixture.InventoryTests.build
 refresh=fixture.InventoryTests.refresh
 refresh_preflight=fixture.InventoryTests.refresh_preflight
 refresh_diagnostic=fixture.InventoryTests.refresh_diagnostic
 setUp=fixture.InventoryTests.setUp
 tearDown=fixture.InventoryTests.tearDown
 frozen=fixture.InventoryTests.frozen
 def snapshot(self):
  conn=self.connect()
  try:
   with contextlib.redirect_stdout(io.StringIO()):return outside.capture(outside.begin_read_only(conn),self.inventory,'PRIVATE-DRIVE',expected_inventory=self.header['inventory_sha256'],proof_args=self.args)
  finally:conn.close()
 def add(self,sid,physical=True):
  self.conn.execute("INSERT INTO m365_bulk_items(drive_id,pending_id,item_id,parent_id,etag,size,status,attempts,next_attempt,updated_at,lease_owner,lease_until,kind) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",('PRIVATE-DRIVE','PRIVATE-FOLDER',sid,'PRIVATE-PARENT','v1',12,'Pending',0,0,0,'',0,'file'))
  if physical:self.inventory[sid]={**self.inventory['s1'],'item_id':sid}
  self.conn.commit()
 def test_two_added_records_have_exact_source_category_version_and_query_bindings(self):
  self.add('PRIVATE-X');self.add('PRIVATE-Y');before=self.frozen();first=self.snapshot();second=self.snapshot()
  self.assertEqual(before,self.frozen());outside.verify_pair(first,second)
  rows=first['summary']['outside_unresolved'];self.assertEqual(len(rows),2)
  self.assertEqual({r['source_id_sha256'] for r in rows},{hashlib.sha256(x.encode()).hexdigest() for x in ('PRIVATE-X','PRIVATE-Y')})
  for row in rows:
   self.assertEqual(row['relation'],'added_physical_identity');self.assertIn(row['current_category'],outside.support.CATEGORIES);self.assertEqual(len(row['search_coverage']),4);self.assertFalse(row['processing_authorized']);self.assertRegex(row['source_version_rights_sha256'],'^[a-f0-9]{64}$')
  self.assertEqual(first['summary']['approved_unresolved_sources'],5);self.assertEqual(first['summary']['preserved_receipt_count'],20)
 def test_nonphysical_record_is_not_claimed_as_one_of_the_physical_additions(self):
  self.add('PRIVATE-NONPHYSICAL',physical=False);row=self.snapshot()['summary']['outside_unresolved'][0]
  self.assertEqual(row['relation'],'outside_baseline');self.assertFalse(row['current_physical_member']);self.assertIsNone(row['current_inventory_row_sha256'])
 def test_previously_available_member_has_distinct_relation(self):
  member={'source_item_id':'PRIVATE-OLD','source_drive_id':'PRIVATE-DRIVE','category':'automatic_retry','current_source':None,'current_inventory_member':False,'availability_exception':False,'exact_complete_text':False,'candidate_versions':[],'candidate_source_provenance':[],'holds':[],'bulk_provenance':[]}
  row=outside.bind_outside(member,{'category':'legacy_available'},{},[0,1,0,1],set(),set())
  self.assertEqual(row['relation'],'baseline_previously_available');self.assertEqual(row['baseline_category'],'legacy_available')
 def test_same_count_identity_swap_cannot_pass_independent_verification(self):
  self.add('PRIVATE-X');self.add('PRIVATE-Y');first=self.snapshot();self.conn.execute("UPDATE m365_bulk_items SET item_id='PRIVATE-Z' WHERE item_id='PRIVATE-Y'");self.conn.commit();del self.inventory['PRIVATE-Y'];self.inventory['PRIVATE-Z']={**self.inventory['s1'],'item_id':'PRIVATE-Z'}
  with self.assertRaisesRegex(ValueError,'OUTSIDE_SOURCE_DRIFT'):outside.verify_pair(first,self.snapshot())
 def test_same_identity_version_or_provenance_drift_cannot_pass(self):
  self.add('PRIVATE-X');self.add('PRIVATE-Y');first=self.snapshot();self.conn.execute("UPDATE m365_bulk_items SET etag='changed-version' WHERE item_id='PRIVATE-Y'");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'OUTSIDE_SOURCE_DRIFT'):outside.verify_pair(first,self.snapshot())
 def test_twentieth_receipt_tamper_is_rejected(self):
  rid=self.review['current_consideration']['receipts'][-1]['receipt_id'];self.conn.execute('UPDATE '+outside.support.RECEIPT_TABLE+' SET matched_count=0 WHERE receipt_id=?',(rid,));self.conn.commit()
  with self.assertRaisesRegex(ValueError,'PRESERVED_RECEIPT_DRIFT'):self.snapshot()
 def test_database_blocks_writes_below_facade(self):
  conn=self.connect()
  try:
   outside.begin_read_only(conn)
   with self.assertRaises(Exception) as got:conn.execute('DELETE FROM m365_bulk_items')
   if getattr(conn,'backend','sqlite')=='postgres':self.assertEqual(got.exception.sqlstate,'25006')
  finally:conn.close()
 def test_controls_changed_between_connections_stop(self):
  first=self.snapshot();self.conn.execute("UPDATE m365_bulk_items SET attempts=attempts+1 WHERE item_id='s2'");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'PROTECTED_PAUSE_HOLD_DRIFT'):outside.verify_pair(first,self.snapshot())
 def test_terminal_source_bindings_do_not_expose_private_values(self):
  self.add('PRIVATE-X');self.add('PRIVATE-Y');first=self.snapshot();pair=outside.verify_pair(first,self.snapshot())
  with contextlib.redirect_stdout(io.StringIO()) as out:outside.emit(first['summary'],pair)
  self.assertNotIn('PRIVATE',out.getvalue());self.assertEqual(out.getvalue().count('OUTSIDE_COHORT_SOURCE='),2)
 def test_any_outside_count_other_than_two_stops(self):
  for count in (0,1,3):
   with self.assertRaisesRegex(ValueError,'OUTSIDE_SCOPE_DRIFT'):outside.validate_boundary({'outside_unresolved':[{'source_id_sha256':str(i)} for i in range(count)]},{})
 def test_new_task_cannot_ignore_its_own_saved_receipts(self):
  old=outside.KEY
  try:
   outside.KEY=outside.OLD_KEY
   with self.assertRaisesRegex(ValueError,'SAVED_OUTPUT_REQUIRES_RECONCILIATION'):outside.saved_targets(outside.ReadOnlyConnection(self.conn))
  finally:outside.KEY=old

@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated PostgreSQL CI only')
class PostgreSQLOutsideTests(OutsideTests):
 connect=fixture.PostgreSQLInventoryTests.connect
 def setUp(self):fixture.PostgreSQLInventoryTests.setUp(self)
 def tearDown(self):fixture.PostgreSQLInventoryTests.tearDown(self)

class PolicyTests(unittest.TestCase):
 def test_new_workflow_is_separate_single_start_and_collects_before_cleanup(self):
  root=Path(__file__).resolve().parents[1];w=(root/'.github/workflows/salcapa-knowledge-outside-cohort.yml').read_text()
  self.assertEqual(w.count('az containerapp job start '),1);self.assertEqual(w.count('az deployment group create '),1)
  self.assertLess(w.index('Collect terminal proof before cleanup'),w.index('Remove and verify isolated task-search job'))
  self.assertIn('salcapa-outside-b48224',w);self.assertNotIn('workflow_dispatch',w)
  self.assertIn('tools/validate_knowledge_outside_cohort.py --verify-log',w)
  self.assertIn('salus-outside-cohort-reconciliation-20261116',w)

if __name__=='__main__':unittest.main()
