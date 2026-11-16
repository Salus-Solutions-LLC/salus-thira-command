"""Schema discovery, complete-only responses, bounded redaction and historical readback."""
import contextlib,copy,importlib.util,io,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import recover_knowledge_outside_cohort_schema as schema
spec=importlib.util.spec_from_file_location('schema_recovery_fixture',Path(__file__).with_name('test_knowledge_outside_cohort_log_recovery.py'));fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
ROOT=Path(__file__).resolve().parents[1];GUID='11111111-2222-3333-4444-555555555555'
class SchemaTests(fixture.RecoveryTests):
 def metadata(self,*names):return {'tables':[{'name':n,'columns':[{'name':k,'type':v} for k,v in schema.SCHEMAS[n].items()]} for n in names]}
 def opener(self,values):
  outer=self
  class Response:
   status=200
   def __init__(self,url,value):self.url=url;self.value=value
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def geturl(self):return self.url
   def read(self,n):return json.dumps(self.value).encode()
  class Opener:
   calls=[]
   def open(self,request,timeout):
    outer.assertEqual(request.get_method(),'GET');outer.assertEqual(timeout,90);outer.assertTrue(request.full_url.startswith('https://api.loganalytics.azure.com/v1/workspaces/'+GUID+'/'));self.calls.append(request.full_url)
    return Response(request.full_url,values[len(self.calls)-1])
  return Opener()
 def result(self):return {'tables':[{'name':'PrimaryResult','columns':[{'name':n} for n in ('TimeGenerated','Replica','Message')],'rows':[['2026-11-16T21:14:22Z',self.reference['execution']+'-pod',r['message']] for r in self.records]}]}
 def test_metadata_selects_only_known_complete_schema_and_avoids_absent_union(self):
  for name in schema.SCHEMAS:
   with contextlib.redirect_stdout(io.StringIO()) as out:selected=schema.select_schemas(self.metadata(name)|{'functions':[{'query':'PRIVATE_FUNCTION'}]})
   self.assertEqual(selected,(name,));q=schema.query(self.reference,selected);self.assertTrue(q.startswith(name+' | '));self.assertNotIn('isfuzzy',q);self.assertNotIn('PRIVATE_FUNCTION',out.getvalue())
 def test_unknown_missing_duplicate_and_incomplete_schemas_stop(self):
  values=[{'tables':[{'name':'PRIVATE_TABLE','columns':[]}]},self.metadata('ContainerAppConsoleLogs','ContainerAppConsoleLogs'),self.metadata('ContainerAppConsoleLogs')]
  values[-1]['tables'][0]['columns'].pop()
  for value in values:
   with contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(schema.RecoveryFailure):schema.select_schemas(value)
 def test_one_metadata_and_two_historical_gets_complete_full_proof(self):
  opener=self.opener([self.metadata('ContainerAppConsoleLogs'),self.result(),self.result()]);budget=schema.Budget()
  with contextlib.redirect_stdout(io.StringIO()) as out:
   selected=schema.select_schemas(schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',budget,opener=opener));first=schema.fetch(GUID,'FICTIONAL_TOKEN',self.reference,selected,budget,opener);second=schema.fetch(GUID,'FICTIONAL_TOKEN',self.reference,selected,budget,opener)
  self.assertEqual(budget.reads,3);self.assertEqual(sum('/metadata' in u for u in opener.calls),1);self.assertEqual(sum('/query?' in u for u in opener.calls),2)
  self.assertEqual(schema.base.reconstruct(self.reference,first)[1],self.rows);self.assertEqual(schema.base.reconstruct(self.reference,second)[1],self.rows);self.assertNotIn('FICTIONAL_TOKEN',out.getvalue())
  with self.assertRaisesRegex(schema.RecoveryFailure,'READ_BUDGET'):schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',budget,opener=opener)
 def test_partial_error_remains_failure_with_bounded_noncontent_diagnostic(self):
  bad=self.result()|{'error':{'code':'PartialError','message':'PRIVATE-ERROR-NAME','innererror':{'code':'SemanticError','message':'PRIVATE-RAW-QUERY'}}};opener=self.opener([bad])
  with contextlib.redirect_stdout(io.StringIO()) as out:
   with self.assertRaisesRegex(schema.RecoveryFailure,'LOG_QUERY_INCOMPLETE'):schema.get_json(GUID,'FICTIONAL_TOKEN','query',schema.Budget(),{'query':'fixed fixture','timespan':'fixed fixture'},opener)
  self.assertIn('PartialError',out.getvalue());self.assertIn('SemanticError',out.getvalue());self.assertNotIn('PRIVATE',out.getvalue());self.assertNotIn('FICTIONAL_TOKEN',out.getvalue());self.assertEqual(len(opener.calls),1)
 def test_absent_or_null_error_is_distinguished_from_non_null_malformed_error(self):
  for value in (self.result(),self.result()|{'error':None}):
   with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',schema.Budget(),opener=self.opener([value])),value)
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaises(schema.RecoveryFailure):schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',schema.Budget(),opener=self.opener([self.result()|{'error':{}}]))
 def test_profile_exposes_codes_shapes_not_raw_names_rows_or_messages(self):
  value={'error':{'code':'PRIVATE_ERROR','message':'PRIVATE_MESSAGE'},'tables':[{'name':'PRIVATE_TABLE','columns':[{'name':'PRIVATE_COLUMN'}],'rows':[['PRIVATE_ROW']]}]};text=json.dumps(schema.profile(value,200))
  self.assertNotIn('PRIVATE',text);self.assertIn('OTHER',text);self.assertIn('row_count',text)
 def test_read_targets_remain_get_only_and_no_cross_workspace_or_unknown_tables(self):
  for endpoint in ('export','query/other','metadata?workspaces=other'):
   with self.assertRaisesRegex(schema.RecoveryFailure,'ENDPOINT_DENIED'):schema.get_json(GUID,'FICTIONAL_TOKEN',endpoint,schema.Budget())
  with self.assertRaisesRegex(schema.RecoveryFailure,'TABLE_SCOPE_DENIED'):schema.query(self.reference,('PRIVATE_TABLE',))
 def test_metadata_permission_denial_never_falls_back_or_retries(self):
  class Denied:
   calls=0
   def open(self,*a,**k):self.calls+=1;raise schema.urllib.error.HTTPError('fixed',403,'PRIVATE_ERROR',None,None)
  denied=Denied()
  with contextlib.redirect_stdout(io.StringIO()) as out:
   with self.assertRaisesRegex(schema.RecoveryFailure,'LOG_ACCESS_DENIED'):schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',schema.Budget(),opener=denied)
  self.assertEqual(denied.calls,1);self.assertNotIn('PRIVATE',out.getvalue())
 def test_http_error_body_retains_only_allowlisted_diagnostic_codes(self):
  class BadQuery:
   def open(self,*a,**k):raise schema.urllib.error.HTTPError('fixed',400,'PRIVATE_REASON',None,io.BytesIO(json.dumps({'error':{'code':'BadArgumentError','message':'PRIVATE_MESSAGE','innererror':{'code':'SemanticError','message':'PRIVATE_QUERY'}}}).encode()))
  with contextlib.redirect_stdout(io.StringIO()) as out:
   with self.assertRaisesRegex(schema.RecoveryFailure,'LOG_HTTP_FAILURE'):schema.get_json(GUID,'FICTIONAL_TOKEN','metadata',schema.Budget(),opener=BadQuery())
  self.assertIn('BadArgumentError',out.getvalue());self.assertIn('SemanticError',out.getvalue());self.assertNotIn('PRIVATE',out.getvalue());self.assertNotIn('FICTIONAL_TOKEN',out.getvalue())
 def test_workflow_contains_no_runtime_resource_or_database_write_command(self):
  w=(ROOT/'.github/workflows/salcapa-knowledge-outside-schema-log-recovery.yml').read_text()
  for bad in ('workflow_dispatch','job start','job create','job delete','deployment group create','role assignment','connect_database','psql '):self.assertNotIn(bad,w)
  self.assertIn("format('salcapa-outside-schema-recovery-pr-{0}', github.event.pull_request.number) || 'salcapa-knowledge-diagnostic'",w)
  self.assertIn('2>/tmp/historical-workspace-error.log',w);self.assertIn('if: always()',w);self.assertIn('salcapa-dev-approval',w)
 @unittest.skipIf(os.name=='nt','Actual Bash guard is exercised in Linux CI')
 def test_actual_pre_azure_guard_rejects_changed_fields_sources_authorities_and_replay(self):
  import yaml
  w=yaml.load((ROOT/'.github/workflows/salcapa-knowledge-outside-schema-log-recovery.yml').read_text(),Loader=yaml.BaseLoader);guard=next(s['run'] for s in w['jobs']['recover']['steps'] if s.get('name')=='Validate exact historical read')
  path='deploy/azure/activations/knowledge-outside-schema-log-recovery-20261116.json';a=json.loads((ROOT/path).read_text())
  self.assertEqual(a['maximum_metadata_reads'],1);self.assertEqual(a['maximum_query_reads'],2);self.assertEqual(a['maximum_total_log_get_reads'],3)
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);target=root/path;target.parent.mkdir(parents=True)
   for name in set(a['source_sha256'])|{b['path'] for b in a['authority_rows']}:
    (root/name).parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,root/name)
   def check(value,attempt='1'):
    target.write_text(json.dumps(value));return subprocess.run(['bash','-euo','pipefail','-c',guard],cwd=root,env={**os.environ,'GITHUB_RUN_ATTEMPT':attempt},capture_output=True,text=True).returncode
   self.assertEqual(check(a),0);self.assertNotEqual(check(a,'2'),0)
   for key in a:self.assertNotEqual(check(a|{key:'altered'}),0,key)
   for name in a['source_sha256']:
    p=root/name;before=p.read_bytes();p.write_bytes(before+b' altered');self.assertNotEqual(check(a),0,name);p.write_bytes(before)
   for b in a['authority_rows']:
    p=root/b['path'];before=p.read_text();lines=before.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('|') and b['needle'] in l);lines[i]+=' altered';p.write_text('\n'.join(lines));self.assertNotEqual(check(a),0,b['needle']);p.write_text(before)
if __name__=='__main__':unittest.main()
