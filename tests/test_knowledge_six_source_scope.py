"""Six-source proposal gates, independent report validation and unchanged DB controls."""
import contextlib,copy,hashlib,importlib.util,io,json,re,unittest
from pathlib import Path
from tools import live_knowledge_six_source_scope as scope
from tools import validate_knowledge_six_source_scope as validator
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('scope_database_fixture',Path(__file__).with_name('test_knowledge_outside_cohort.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

def production_fixture():
 """Retained historical report is a test fixture, never a new live observation."""
 ref=json.loads((ROOT/'deploy/azure/activations/knowledge-outside-cohort-log-reference-20261116.json').read_text())
 messages=[r['message'] for r in ref['console_records']]
 values={m.split('=',1)[0]:m.split('=',1)[1] for m in messages}
 def val(k):return values['INVENTORY_RECON_'+('approved_critical_drift_sources' if k=='critical_drift_sources' else k).upper()]
 def integer(k):return int(val(k))
 rows=copy.deepcopy(scope.REFERENCE_ROWS)
 pair={k[len('INVENTORY_RECON_READBACK_'):].lower():(int(v) if v.isdigit() else v) for k,v in values.items() if k.startswith('INVENTORY_RECON_READBACK_')}
 summary={k:integer(k) for k in ('physical_files','represented_files','unresolved_files','approved_unresolved_sources','current_paused_sources','current_hold_sources','paused_membership_changed','hold_membership_changed','critical_drift_sources','missing_representation')}
 summary.update({k:val(k) for k in ('inventory_sha256','source_differences_sha256','search_matrix_sha256','preserved_receipts_sha256')})
 summary.update(outside_unresolved=rows,preserved_receipt_count=20,source_differences=[json.loads(m.split('=',1)[1]) for m in messages if m.startswith('INVENTORY_RECON_SOURCE_DELTA=')],protected_checkpoints={'sha256':val('protected_checkpoint_sha256'),'extraction_rows':0,'bulk_rows':0},at='2026-11-16T21:14:22+00:00')
 summary['queries']=[{'label':label,'query_sha256':hashlib.sha256(query.encode()).hexdigest(),'considered_count':summary['represented_files'],'matched_count':integer('query_'+label+'_matched')} for label,query in scope.QUERIES]
 summary['current_unresolved_categories']={k:integer('current_category_'+k) for k in scope.support.CATEGORIES}
 messages+=['OUTSIDE_COHORT_SOURCE='+scope.support.canonical(row) for row in rows]
 messages+=['OUTSIDE_COHORT_COUNT=6','OUTSIDE_COHORT_SHA256='+scope.REFERENCE_SOURCE_SHA256,'OUTSIDE_COHORT_VERIFIED=1']
 return summary,pair,messages

class ScopeTests(unittest.TestCase):
 def setUp(self):self.summary,self.pair,self.messages=production_fixture()
 def proposal(self,summary=None,pair=None):
  with contextlib.redirect_stdout(io.StringIO()):
   return scope.prepare_proposal(summary or self.summary,pair or self.pair,run_id='43967758804',script_sha256=hashlib.sha256((ROOT/'tools/live_knowledge_six_source_scope.py').read_bytes()).hexdigest())
 def log(self,p):
  fields=['SCOPE_PROPOSAL_JSON='+scope.support.canonical(p),'SCOPE_PROPOSAL_SHA256='+scope.support.digest(p),'SCOPE_PROPOSAL_COMPLETE=1']
  return '\n'.join('2026-11-16T21:14:22Z stdout F '+m for m in self.messages+fields)
 def test_addendum_binds_six_sources_without_adopting_or_extending_parent(self):
  before=copy.deepcopy(self.summary);p=self.proposal()
  self.assertEqual(self.summary,before);self.assertEqual(p['proposed_additional_sources'],6)
  self.assertEqual(p['approved_roster_sources'],8430);self.assertEqual(p['approved_parent_batches'],200)
  self.assertTrue(all(v is False for v in p['authority'].values()))
  self.assertEqual(scope.support.digest(p['sources']),scope.REFERENCE_SOURCE_SHA256)
  self.assertEqual(validator.verify_log(self.log(p))['SCOPE_PROPOSAL_SHA256'],scope.support.digest(p))
 def test_each_source_binding_change_stops_instead_of_refreshing(self):
  for row in range(6):
   for key in self.summary['outside_unresolved'][row]:
    changed=copy.deepcopy(self.summary);changed['outside_unresolved'][row][key]='changed'
    with self.subTest(row=row,key=key):
     with self.assertRaises(Exception):self.proposal(changed)
 def test_missing_duplicate_seventh_and_reordered_identities_stop(self):
  rows=self.summary['outside_unresolved']
  for changed_rows in (rows[:-1],rows+[rows[0]],rows[:-1]+[rows[0]],list(reversed(rows))):
   s=copy.deepcopy(self.summary);s['outside_unresolved']=changed_rows
   with self.assertRaises(Exception):self.proposal(s)
 def test_receipts_holds_pauses_checkpoints_approved_scope_and_independent_drift_stop(self):
  for key,value in [('preserved_receipts_sha256','0'*64),('current_paused_sources',732),('current_hold_sources',92),('critical_drift_sources',1),('unresolved_files',8437),('approved_unresolved_sources',8431),('missing_representation',1)]:
   s=copy.deepcopy(self.summary);s[key]=value
   with self.subTest(key=key):
    with self.assertRaises(Exception):self.proposal(s)
  s=copy.deepcopy(self.summary);s['protected_checkpoints']['sha256']='0'*64
  with self.assertRaises(Exception):self.proposal(s)
  for key in ('outside_approved_sources_changed','represented_added','represented_removed'):
   p=copy.deepcopy(self.pair);p[key]=1
   with self.assertRaises(Exception):self.proposal(pair=p)
 def test_invalid_execution_binding_stops(self):
  for run,sha in [('0','a'*64),('43967758804','bad'),('43967758804;evil','a'*64)]:
   with contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(Exception):scope.prepare_proposal(self.summary,self.pair,run_id=run,script_sha256=sha)
 def test_collector_rejects_absence_duplicates_truncation_and_recomputed_tampering(self):
  p=self.proposal();text=self.log(p);lines=text.splitlines()
  for changed in ('\n'.join(lines[:-1]),text+'\n'+lines[-1],text[:-30]):
   with self.assertRaises(Exception):validator.verify_log(changed)
  for key in p['authority']:
   changed=copy.deepcopy(p);changed['authority'][key]=True
   with self.assertRaises(Exception):validator.verify_log(self.log(changed))
  for key in p['effects']:
   changed=copy.deepcopy(p);changed['effects'][key]=1
   with self.assertRaises(Exception):validator.verify_log(self.log(changed))
  for key in ('inventory_sha256','source_differences_sha256','search_matrix_sha256','preserved_receipts_sha256'):
   changed=copy.deepcopy(p);changed['current_observation'][key]='0'*64
   with self.assertRaises(Exception):validator.verify_log(self.log(changed))
 def test_output_only_hashes_and_explicit_approval_gates(self):
  p=self.proposal()
  with contextlib.redirect_stdout(io.StringIO()) as out:scope.emit_proposal(p)
  self.assertEqual(out.getvalue().count('SCOPE_PROPOSAL_JSON='),1)
  self.assertNotIn('source_item_id',out.getvalue());self.assertNotIn('source_drive_id',out.getvalue())
  self.assertLess(len(scope.support.canonical(p).encode()),16384)
  self.assertIn('Exact proposal manifest approval',p['next_approval'])
 def test_actual_workflow_retains_proposal_and_sources_before_cleanup(self):
  text=(ROOT/'.github/workflows/salcapa-knowledge-six-source-scope.yml').read_text()
  self.assertIn('OUTSIDE_COHORT|OUTSIDE_DRIFT|SCOPE_PROPOSAL)',text)
  self.assertIn('tools/validate_knowledge_six_source_scope.py --verify-log',text)
  self.assertIn('always_collect_before_cleanup',text)
  self.assertIn('TASK_KNOWLEDGE_APPLICATION_AND_WORKER_UNCHANGED=1',text)
  self.assertIn('TASK_KNOWLEDGE_ISOLATED_JOB_REMOVED=1',text)
  self.assertIn('TASK_KNOWLEDGE_FIXED_TEMPORARY_FILES_CLEARED=1',text)
  self.assertIn('TASK_KNOWLEDGE_CREDENTIALS_CLEARED=1',text)

class ScopeDatabaseTests(fixture.OutsideTests):
 """Exercise actual new module captures against genuine database read-only transactions."""
 def snapshot(self):
  conn=self.connect()
  try:
   with contextlib.redirect_stdout(io.StringIO()):return scope.capture(scope.begin_read_only(conn),self.inventory,'PRIVATE-DRIVE',expected_inventory=self.header['inventory_sha256'],proof_args=self.args)
  finally:conn.close()
 def test_new_task_own_receipts_are_checked(self):
  old=scope.KEY
  try:
   scope.KEY=scope.OLD_KEY
   with self.assertRaisesRegex(ValueError,'SAVED_OUTPUT_REQUIRES_RECONCILIATION'):scope.saved_targets(scope.ReadOnlyConnection(self.conn))
  finally:scope.KEY=old

@unittest.skipUnless(__import__('os').getenv('TEST_POSTSEARCH_POSTGRES')=='1','dedicated PostgreSQL CI only')
class PostgreSQLScopeDatabaseTests(ScopeDatabaseTests):
 connect=fixture.PostgreSQLOutsideTests.connect
 def setUp(self):fixture.PostgreSQLOutsideTests.setUp(self)
 def tearDown(self):fixture.PostgreSQLOutsideTests.tearDown(self)

if __name__=='__main__':unittest.main()

