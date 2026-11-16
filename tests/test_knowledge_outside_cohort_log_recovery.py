"""Historical GET correlation, missing source proof, certified order, privacy and actual collector."""
import contextlib,copy,hashlib,io,json,os,re,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import recover_knowledge_outside_cohort_log as recovery
ROOT=Path(__file__).resolve().parents[1]
class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.reference=json.loads((ROOT/recovery.REFERENCE).read_text(encoding='utf-8'))
  deltas=[json.loads(r['message'].split('=',1)[1]) for r in self.reference['console_records'] if r['message'].startswith('INVENTORY_RECON_SOURCE_DELTA=')]
  # Fictional source/version/rights bindings; never an assertion about the real missing six identities.
  self.rows=[{'source_id_sha256':r['source_id_sha256'],'relation':'added_physical_identity','baseline_category':'outside_baseline','baseline_physical_member':False,'current_physical_member':True,'current_category':'automatic_retry','availability_exception':False,'exact_complete_text':False,'paused':False,'held':False,'candidate_count':1,'source_version_rights_sha256':'a'*64,'current_inventory_row_sha256':r['current_row_sha256'],'candidate_versions_sha256':'b'*64,'provenance_sha256':'c'*64,'holds_sha256':'d'*64,'search_coverage':[True,False,True,False],'next_approval':'separate_baseline_scope_and_remediation_approval','processing_authorized':False} for r in deltas[:6]]
  messages=['OUTSIDE_COHORT_SOURCE='+json.dumps(r,sort_keys=True,separators=(',',':')) for r in self.rows]
  messages+=['OUTSIDE_COHORT_COUNT=6','OUTSIDE_COHORT_SHA256='+recovery.digest(self.rows),'OUTSIDE_COHORT_VERIFIED=1','OUTSIDE_DRIFT_OBSERVED_PHYSICAL_FILES=23768','OUTSIDE_DRIFT_OBSERVED_REPRESENTED_FILES=23778','OUTSIDE_DRIFT_OBSERVED_UNRESOLVED_FILES=8436','OUTSIDE_DRIFT_OBSERVED_OUTSIDE_UNRESOLVED=6']
  self.records=[{'time':'2026-11-16T21:14:22Z','message':v} for v in messages]
 def test_reference_is_the_filtered_report_and_cannot_pass_full_proof_alone(self):
  self.assertFalse(self.reference['complete_outside_source_bindings_retained'])
  with self.assertRaisesRegex(recovery.RecoveryFailure,'SOURCE_BINDINGS_MISSING'):recovery.reconstruct(self.reference,[])
 def test_same_timestamp_out_of_order_events_restore_only_digest_certified_order(self):
  text,rows,proof=recovery.reconstruct(self.reference,list(reversed(self.records)))
  self.assertEqual(rows,self.rows);self.assertEqual(proof['source_sha256'],recovery.digest(self.rows));self.assertEqual(text.count('OUTSIDE_COHORT_SOURCE='),6)
 def test_identical_dual_route_copies_dedupe_but_contradiction_stops(self):
  _,rows,proof=recovery.reconstruct(self.reference,self.records+self.records);self.assertEqual(rows,self.rows);self.assertEqual(proof['retrieved_rows'],26)
  with self.assertRaisesRegex(recovery.RecoveryFailure,'CONTRADICTORY_LOG_VALUE'):recovery.reconstruct(self.reference,self.records+[{'time':'2026-11-16T21:14:22Z','message':'OUTSIDE_COHORT_COUNT=7'}])
 def test_missing_tampered_or_non_six_sources_never_pass(self):
  for records in (self.records[1:],self.records+[self.records[0]|{'message':'OUTSIDE_COHORT_SOURCE='+json.dumps(self.rows[0]|{'source_id_sha256':'e'*64})}]):
   with self.assertRaises(recovery.RecoveryFailure):recovery.reconstruct(self.reference,records)
  rows=copy.deepcopy(self.rows);rows[0]['candidate_versions_sha256']='e'*64;records=copy.deepcopy(self.records);records[0]['message']='OUTSIDE_COHORT_SOURCE='+json.dumps(rows[0])
  with self.assertRaisesRegex(recovery.RecoveryFailure,'SOURCE_BINDING_DIGEST_MISMATCH'):recovery.reconstruct(self.reference,records)
 def test_reference_scope_and_observation_mismatch_stop(self):
  for key,value in [('source_run',1),('execution','other'),('window_end','2026-11-17T00:00:00Z')]:
   with self.assertRaisesRegex(recovery.RecoveryFailure,'REFERENCE_SCOPE'):recovery.query(self.reference|{key:value})
  records=[r|{'message':'OUTSIDE_DRIFT_OBSERVED_UNRESOLVED_FILES=8437'} if r['message'].startswith('OUTSIDE_DRIFT_OBSERVED_UNRESOLVED_FILES=') else r for r in self.records]
  with self.assertRaisesRegex(recovery.RecoveryFailure,'OBSERVATION_MISMATCH'):recovery.reconstruct(self.reference,records)
 def test_get_only_exact_host_window_execution_no_cross_workspace(self):
  class Response:
   status=200
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def geturl(inner):return inner.url
   def read(inner,count):return json.dumps({'tables':[{'columns':[{'name':n} for n in ('TimeGenerated','Replica','Message')],'rows':[['2026-11-16T21:14:22Z',self.reference['execution']+'-pod',r['message']] for r in self.records]}]}).encode()
  class Opener:
   def open(inner,request,timeout):
    self.assertEqual(request.get_method(),'GET');self.assertEqual(timeout,90);self.assertTrue(request.full_url.startswith('https://api.loganalytics.azure.com/v1/workspaces/'));self.assertNotIn('workspaces=',request.full_url)
    response=Response();response.url=request.full_url;return response
  result=recovery.fetch('11111111-2222-3333-4444-555555555555','FICTIONAL_TOKEN',self.reference,Opener());self.assertEqual(len(result),13)
  with self.assertRaisesRegex(recovery.RecoveryFailure,'WORKSPACE_INVALID'):recovery.fetch('bad/workspace','FICTIONAL_TOKEN',self.reference,Opener())
 def test_denial_and_redirect_do_not_retry_or_disclose_token(self):
  class Denied:
   calls=0
   def open(inner,*args,**kwargs):inner.calls+=1;raise recovery.urllib.error.HTTPError('https://api.loganalytics.azure.com',403,'PRIVATE_ERROR',None,None)
  denied=Denied()
  with self.assertRaisesRegex(recovery.RecoveryFailure,'LOG_ACCESS_DENIED'):recovery.fetch('11111111-2222-3333-4444-555555555555','FICTIONAL_TOKEN',self.reference,denied)
  self.assertEqual(denied.calls,1)
  with self.assertRaisesRegex(recovery.RecoveryFailure,'REDIRECT_DENIED'):recovery.NoRedirect().redirect_request(None,None,302,None,None,None)
 def test_unknown_raw_message_cannot_be_published(self):
  with self.assertRaisesRegex(recovery.RecoveryFailure,'UNEXPECTED_LOG_KEY'):recovery.reconstruct(self.reference,self.records+[{'time':'2026-11-16T21:14:22Z','message':'OUTSIDE_COHORT_PRIVATE=PRIVATE-NAME'}])
 def test_actual_collector_retains_full_report_and_old_filter_reproduces_the_defect(self):
  text,_,_=recovery.reconstruct(self.reference,self.records);w=(ROOT/'.github/workflows/salcapa-knowledge-outside-cohort-drift.yml').read_text();pattern=re.search("grep -E '([^']+)' /tmp/task-knowledge-search.log",w)[1]
  kept='\n'.join(l for l in text.splitlines() if re.search(pattern,l));recovery.verify_log(kept)
  broken=pattern.replace('|OUTSIDE_COHORT|OUTSIDE_DRIFT','');lost='\n'.join(l for l in text.splitlines() if re.search(broken,l))
  with self.assertRaises(AssertionError):recovery.verify_log(lost)
  if os.name!='nt' and shutil.which('grep'):
   result=subprocess.run(['grep','-E',pattern],input=text,text=True,capture_output=True,check=True);recovery.verify_log(result.stdout)
 def test_workflow_contains_no_runtime_resource_or_database_write_command(self):
  w=(ROOT/'.github/workflows/salcapa-knowledge-outside-log-recovery.yml').read_text()
  self.assertNotIn('workflow_dispatch',w)
  for prohibited in ('job start','job create','job delete','deployment group create','role assignment','psql ','connect_database','az monitor diagnostic-settings create'):self.assertNotIn(prohibited,w)
  self.assertIn('if: always()',w);self.assertIn('salcapa-dev-approval',w)
  self.assertIn("format('salcapa-outside-log-recovery-pr-{0}', github.event.pull_request.number) || 'salcapa-knowledge-diagnostic'",w)
 @unittest.skipIf(os.name=='nt','Actual Bash guard is exercised in Linux CI')
 def test_actual_pre_azure_guard_rejects_changed_fields_sources_authorities_and_replay(self):
  import yaml
  workflow=yaml.load((ROOT/'.github/workflows/salcapa-knowledge-outside-log-recovery.yml').read_text(),Loader=yaml.BaseLoader)
  guard=next(s['run'] for s in workflow['jobs']['recover']['steps'] if s.get('name')=='Validate exact historical read')
  activation_path='deploy/azure/activations/knowledge-outside-log-recovery-20261116.json';activation=json.loads((ROOT/activation_path).read_text())
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/activation_path;target.parent.mkdir(parents=True)
   for path in set(activation['source_sha256'])|{b['path'] for b in activation['authority_rows']}:
    (root/path).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/path,root/path)
   def check(value,attempt='1'):
    target.write_text(json.dumps(value));return subprocess.run(['bash','-euo','pipefail','-c',guard],cwd=root,env={**os.environ,'GITHUB_RUN_ATTEMPT':attempt},capture_output=True,text=True).returncode
   self.assertEqual(check(activation),0);self.assertNotEqual(check(activation,'2'),0)
   for key in activation:self.assertNotEqual(check(activation|{key:'altered'}),0,key)
   for path in activation['source_sha256']:
    p=root/path;before=p.read_bytes();p.write_bytes(before+b' altered');self.assertNotEqual(check(activation),0,path);p.write_bytes(before)
   for b in activation['authority_rows']:
    p=root/b['path'];before=p.read_text();lines=before.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('|') and b['needle'] in l);lines[i]+=' altered';p.write_text('\n'.join(lines));self.assertNotEqual(check(activation),0,b['needle']);p.write_text(before)
if __name__=='__main__':unittest.main()
