"""GET-only retry bounds, Retry-After, URL scope, no redirects and no replay."""
import contextlib,io,json,unittest
from datetime import datetime,timezone
from email.message import Message
from pathlib import Path
import tempfile
from unittest.mock import patch
from urllib.error import HTTPError,URLError
from tools import knowledge_inventory_azure_transport as t
URL='https://management.azure.com/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-salcapa-dev/providers/Microsoft.App/jobs/task/executions/one?api-version=2026-07-01'
class Response:
 status=200
 def __init__(self,value):self.raw=json.dumps(value).encode()
 def __enter__(self):return self
 def __exit__(self,*args):pass
 def read(self,size):return self.raw[:size]
class Clock:
 def __init__(self):self.now=0;self.delays=[]
 def __call__(self):return self.now
 def sleep(self,n):self.delays.append(n);self.now+=n
class Opener:
 def __init__(self,rows):self.rows=list(rows);self.requests=[]
 def open(self,request,timeout):
  self.requests.append(request)
  row=self.rows.pop(0)
  if isinstance(row,Exception):raise row
  return Response(row)
def error(code,delay=None):
 headers=Message()
 if delay is not None:headers['Retry-After']=str(delay)
 return HTTPError(URL,code,'PRIVATE-ERROR',headers,io.BytesIO(b'PRIVATE-BODY'))
class TransportTests(unittest.TestCase):
 def reader(self,rows):
  clock=Clock();opener=Opener(rows);reader=t.ArmReader('PRIVATE-TOKEN',opener=opener,clock=clock,sleep=clock.sleep);return reader,opener,clock
 def test_retries_only_get_and_respects_retry_after_without_logging_secrets(self):
  r,o,c=self.reader([error(429,17),{'value':[]}])
  with contextlib.redirect_stdout(io.StringIO()) as out:self.assertEqual(r.get(URL),{'value':[]})
  self.assertEqual(c.delays,[17]);self.assertEqual([x.get_method() for x in o.requests],['GET','GET']);self.assertNotIn('PRIVATE',out.getvalue())
 def test_defers_when_server_delay_exceeds_budget(self):
  r,o,c=self.reader([error(429,121)])
  with self.assertRaisesRegex(t.TransportFailure,'ARM_RETRY_DEFERRED'):r.get(URL)
  self.assertEqual(len(o.requests),1);self.assertEqual(c.delays,[])
 def test_retries_are_bounded(self):
  r,o,c=self.reader([error(429)]*5)
  with contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaisesRegex(t.TransportFailure,'ARM_READ_RETRY_LIMIT'):r.get(URL)
  self.assertEqual(len(o.requests),5);self.assertEqual(c.delays,[5,10,20,40])
 def test_auth_and_permission_denials_are_not_retried(self):
  for status in (400,401,403,409,302):
   r,o,c=self.reader([error(status)])
   with self.assertRaisesRegex(t.TransportFailure,'ARM_HTTP_'+str(status)):r.get(URL)
   self.assertEqual(len(o.requests),1);self.assertEqual(c.delays,[])
 def test_404_is_explicit_and_not_a_successful_execution(self):
  r,o,c=self.reader([error(404)]);self.assertIsNone(r.get(URL,allow_missing=True))
 def test_network_retry_is_get_only(self):
  r,o,c=self.reader([URLError('PRIVATE'),{'ok':True}])
  with contextlib.redirect_stdout(io.StringIO()):self.assertTrue(r.get(URL)['ok'])
  self.assertEqual(c.delays,[5])
 def test_foreign_hosts_scopes_query_or_methods_are_rejected(self):
  for url in (URL.replace('management.azure.com','evil.example'),URL.replace('https:','http:'),URL.replace('rg-salcapa-dev','rg-production'),URL+'&token=PRIVATE',URL.replace('/jobs/task','/jobs/../task'),URL.replace('Microsoft.App','Microsoft.Storage')):
   with self.assertRaises(t.TransportFailure):t.validate_url(url)
 def test_redirect_handler_never_forwards_authentication(self):self.assertIsNone(t.NoRedirect().redirect_request(None,None,302,'PRIVATE',{},'https://evil.example'))
 def test_http_date_retry_after(self):self.assertEqual(t.retry_delay('Mon, 16 Nov 2026 19:01:00 GMT',0,lambda:datetime(2026,11,16,19,0,tzinfo=timezone.utc)),60)
 def test_invalid_retry_after_fails_closed(self):
  for value in ('PRIVATE','NaN','inf'):
   with self.assertRaises(t.TransportFailure):t.retry_delay(value,0)
 def test_discovery_requires_exactly_one_safe_execution(self):
  for rows in ([],[{'name':'one'}],[{'name':'one'},{'name':'two'}],[{'name':'PRIVATE / x'}]):
   r,_,_=self.reader([{'value':rows}])
   if not rows:self.assertIsNone(t.discover(r,URL))
   elif len(rows)==1 and rows[0]['name']=='one':self.assertEqual(t.discover(r,URL),'one')
   else:
    with self.assertRaises(t.TransportFailure):t.discover(r,URL)
 def test_discovery_rejects_unbounded_pagination(self):
  r,_,_=self.reader([{'value':[{'name':'one'}],'nextLink':'PRIVATE'}])
  with self.assertRaises(t.TransportFailure):t.discover(r,URL)
 def test_wait_retries_read_without_any_start_or_submit(self):
  r,o,c=self.reader([error(429,5),{'properties':{'status':'Running'}},{'properties':{'status':'Succeeded'}}])
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):t.wait(r,URL,kind='execution',seconds=60,output=Path(folder)/'state.json',clock=c,sleep=c.sleep)
  self.assertEqual(len(o.requests),3);self.assertTrue(all(x.get_method()=='GET' for x in o.requests))
 def test_wait_failure_is_not_misreported_as_success(self):
  r,_,c=self.reader([{'properties':{'status':'Failed'}}])
  with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()):
   with self.assertRaisesRegex(t.TransportFailure,'ARM_EXECUTION_FAILED'):t.wait(r,URL,kind='execution',seconds=60,output=Path(folder)/'state.json',clock=c,sleep=c.sleep)
 def test_discovery_cli_saves_identity_without_mixing_retry_telemetry(self):
  with tempfile.TemporaryDirectory() as folder,patch.object(t,'access_token',return_value='PRIVATE'),patch.object(t,'discover',return_value='one'),patch('sys.argv',['transport','discover','--url',URL,'--output',str(Path(folder)/'name.txt')]),contextlib.redirect_stdout(io.StringIO()) as out:
   t.main();self.assertEqual((Path(folder)/'name.txt').read_text(),'one');self.assertEqual(out.getvalue(),'')
 def test_namespace_absence_checks_all_pages(self):
  url=URL.split('/jobs/')[0]+'/jobs?api-version=2025-07-01';nexturl=url+'&$skiptoken=next'
  r,o,_=self.reader([{'value':[],'nextLink':nexturl},{'value':[]}]);t.verify_absence(r,url,'task');self.assertEqual(len(o.requests),2)
 def test_namespace_presence_on_later_page_blocks_absence_claim(self):
  url=URL.split('/jobs/')[0]+'/jobs?api-version=2025-07-01'
  r,_,_=self.reader([{'value':[],'nextLink':url+'&$skiptoken=next'},{'value':[{'name':'task'}]}])
  with self.assertRaisesRegex(t.TransportFailure,'ARM_NAMESPACE_NOT_EMPTY'):t.verify_absence(r,url,'task')
 def test_namespace_pagination_cannot_leave_scope(self):
  url=URL.split('/jobs/')[0]+'/jobs?api-version=2025-07-01';r,_,_=self.reader([{'value':[],'nextLink':url.replace('management.azure.com','evil.example')}])
  with self.assertRaises(t.TransportFailure):t.verify_absence(r,url,'task')

class RecoveryWorkflowTests(unittest.TestCase):
 def test_single_submit_start_and_always_collection_before_cleanup(self):
  root=Path(__file__).resolve().parent.parent;w=(root/'.github/workflows/salcapa-knowledge-inventory-reconciliation-recovery.yml').read_text()
  self.assertEqual(w.count('az containerapp job start '),1);self.assertEqual(w.count('az deployment group create --no-wait '),1)
  self.assertIn('id: execute\n        continue-on-error: true',w)
  self.assertIn('- name: Collect terminal proof before cleanup\n        if: always()',w);self.assertLess(w.index('- name: Collect terminal proof'),w.index('- name: Remove and verify'))
 def test_payload_and_limits_unchanged_and_cleanup_owner_matches_bicep(self):
  root=Path(__file__).resolve().parent.parent;old=json.loads((root/'deploy/azure/activations/knowledge-inventory-reconciliation-20261116.json').read_text());new=json.loads((root/'deploy/azure/activations/knowledge-inventory-reconciliation-recovery-20261116.json').read_text())
  self.assertEqual(new['payload_sha256'],old['payload_sha256']);self.assertEqual(new['source_sha256']['tools/live_knowledge_inventory_reconciliation.py'],old['source_sha256']['tools/live_knowledge_inventory_reconciliation.py'])
  for k in ('execution_cpu','execution_memory','max_execution_seconds','maximum_observed_peak_rss_kib'):self.assertEqual(new[k],old[k])
  w=(root/'.github/workflows/salcapa-knowledge-inventory-reconciliation-recovery.yml').read_text();b=(root/'infra/azure/knowledge-inventory-reconciliation-recovery-job.bicep').read_text()
  self.assertIn('salusTaskKey: \''+new['task_key']+'\'',b);self.assertIn('= "'+new['task_key']+'"',w)
 def test_existing_report_validation_is_unchanged(self):
  import inspect
  from tools import validate_knowledge_inventory as old,validate_knowledge_inventory_recovery as new
  self.assertEqual(inspect.getsource(old.verify_log),inspect.getsource(new.verify_log))
if __name__=='__main__':unittest.main()
