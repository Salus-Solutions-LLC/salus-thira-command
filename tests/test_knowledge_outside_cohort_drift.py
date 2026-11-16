"""Measure bounded current membership without adopting a new recovery roster."""
import contextlib,copy,importlib.util,io,os,unittest
from pathlib import Path
from tools import live_knowledge_outside_cohort_drift as drift
spec=importlib.util.spec_from_file_location('drift_outside_fixture',Path(__file__).with_name('test_knowledge_outside_cohort.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class DriftTests(unittest.TestCase):
 connect=fixture.OutsideTests.connect;insert=fixture.OutsideTests.insert;save=fixture.OutsideTests.save;build=fixture.OutsideTests.build;refresh=fixture.OutsideTests.refresh;refresh_preflight=fixture.OutsideTests.refresh_preflight;refresh_diagnostic=fixture.OutsideTests.refresh_diagnostic;setUp=fixture.OutsideTests.setUp;tearDown=fixture.OutsideTests.tearDown;add=fixture.OutsideTests.add;frozen=fixture.OutsideTests.frozen
 def snapshot(self):
  conn=self.connect()
  try:
   with contextlib.redirect_stdout(io.StringIO()):return drift.capture(drift.begin_read_only(conn),self.inventory,'PRIVATE-DRIVE',expected_inventory=self.header['inventory_sha256'],proof_args=self.args)
  finally:conn.close()
 def test_six_current_outside_identities_are_reported_without_inventing_historical_two(self):
  for i in range(6):self.add('PRIVATE-'+str(i))
  before=self.frozen();first=self.snapshot();second=self.snapshot();pair=drift.verify_pair(first,second)
  self.assertEqual(self.frozen(),before);self.assertEqual(len(first['summary']['outside_unresolved']),6);self.assertEqual(first['summary']['approved_unresolved_sources'],5);self.assertEqual(first['summary']['preserved_receipt_count'],20)
  with contextlib.redirect_stdout(io.StringIO()) as out:drift.emit(first['summary'],pair)
  self.assertEqual(out.getvalue().count('OUTSIDE_COHORT_SOURCE='),6);self.assertNotIn('PRIVATE',out.getvalue())
 def unit_boundary(self,count):
  # Synthetic production-sized scalar fixture: source rows still come from actual read-only fixture captures.
  for i in range(count):self.add('PRIVATE-'+str(i))
  first=self.snapshot();s=first['summary'];s.update(physical_files=23761,represented_files=23771,unresolved_files=8430+count,approved_unresolved_sources=8430,preserved_receipts_sha256='21c4bcd816686d4178c32bf224228c13639aa56a8225cf0cd3219af6fab0cd1f',current_paused_sources=733,current_hold_sources=93,paused_membership_changed=0,hold_membership_changed=0)
  s['protected_checkpoints']['sha256']='214f2756ca0bc179bfaed880480113b5cd31cecd9de0e803e03013bcd4872ac7'
  return s,{'outside_approved_sources_changed':0,'represented_added':0,'represented_removed':0}
 def test_count_drift_within_readonly_bound_is_measured_not_adopted(self):
  s,p=self.unit_boundary(6)
  with contextlib.redirect_stdout(io.StringIO()) as out:drift.validate_boundary(s,p)
  self.assertIn('OUTSIDE_DRIFT_OBSERVED_OUTSIDE_UNRESOLVED=6',out.getvalue());self.assertFalse(s['baseline_adopted']);self.assertEqual(s['new_receipts'],0)
 def test_eleventh_outside_source_stops_after_sanitized_observation(self):
  s,p=self.unit_boundary(11)
  with contextlib.redirect_stdout(io.StringIO()) as out:
   with self.assertRaisesRegex(ValueError,'OUTSIDE_SCOPE_DRIFT'):drift.validate_boundary(s,p)
  self.assertIn('OUTSIDE_DRIFT_OBSERVED_OUTSIDE_UNRESOLVED=11',out.getvalue());self.assertNotIn('VERIFIED=1',out.getvalue())
 def test_protected_controls_and_approved_critical_drift_still_stop(self):
  s,p=self.unit_boundary(2)
  for key,value in [('critical_drift_sources',1),('current_paused_sources',732),('current_hold_sources',92),('preserved_receipts_sha256','0'*64)]:
   changed=copy.deepcopy(s);changed[key]=value
   with contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaisesRegex(ValueError,'OUTSIDE_PRIOR_BOUNDARY_DRIFT'):drift.validate_boundary(changed,p)
 def test_count_only_readback_cannot_hide_changed_source(self):
  self.add('PRIVATE-X');first=self.snapshot();self.conn.execute("UPDATE m365_bulk_items SET etag='v2' WHERE item_id='PRIVATE-X'");self.conn.commit()
  with self.assertRaisesRegex(ValueError,'OUTSIDE_SOURCE_DRIFT'):drift.verify_pair(first,self.snapshot())
 def test_twenty_receipts_and_database_enforced_readonly(self):
  conn=self.connect()
  try:
   ro=drift.begin_read_only(conn);self.assertEqual(drift.input_proof(ro,**self.args)[0]['unresolved_files'],5)
   with self.assertRaises(Exception):conn.execute('DELETE FROM m365_bulk_items')
  finally:conn.close()
 def test_total_census_and_outside_membership_must_reconcile(self):
  s,p=self.unit_boundary(2);s['unresolved_files']+=1
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaisesRegex(ValueError,'OUTSIDE_SCOPE_DRIFT'):drift.validate_boundary(s,p)
 def test_independent_outside_changes_and_large_output_stop(self):
  s,p=self.unit_boundary(2);p['outside_approved_sources_changed']=1
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaisesRegex(ValueError,'OUTSIDE_READBACK_DRIFT'):drift.validate_boundary(s,p)
  p['outside_approved_sources_changed']=0;s['outside_unresolved'][0]['oversized_fixture']='X'*131073
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaisesRegex(ValueError,'DELTA_REPORT_BOUND'):drift.validate_boundary(s,p)

@unittest.skipUnless(os.getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated PostgreSQL CI only')
class PostgreSQLDriftTests(DriftTests):
 connect=fixture.PostgreSQLOutsideTests.connect
 def setUp(self):fixture.PostgreSQLOutsideTests.setUp(self)
 def tearDown(self):fixture.PostgreSQLOutsideTests.tearDown(self)

if __name__=='__main__':unittest.main()
