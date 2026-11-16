"""GET-only recovery of omitted telemetry from one completed execution; no job/DB access."""
import argparse,hashlib,itertools,json,re,subprocess,sys,urllib.error,urllib.parse,urllib.request
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.validate_knowledge_outside_cohort_drift import verify_log
REFERENCE='deploy/azure/activations/knowledge-outside-cohort-log-reference-20261116.json'
class RecoveryFailure(ValueError):pass
def need(value,code):
 if not value:raise RecoveryFailure(code)
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def query(reference):
 need(reference['execution']=='salcapa-outdrift-b48224-3tcgdet' and reference['source_run']==43955840933 and reference['source_job']==133610096637,'REFERENCE_SCOPE')
 need(reference['window_start']=='2026-11-16T21:02:00Z' and reference['window_end']=='2026-11-16T21:16:00Z' and reference['expected_outside_count']==6,'REFERENCE_SCOPE')
 return "union isfuzzy=true ContainerAppConsoleLogs_CL, ContainerAppConsoleLogs | where TimeGenerated between (datetime(2026-11-16T21:02:00Z) .. datetime(2026-11-16T21:16:00Z)) | extend Replica=coalesce(tostring(column_ifexists('ContainerGroupName_s','')),tostring(column_ifexists('ContainerGroupName',''))), Message=coalesce(tostring(column_ifexists('Log_s','')),tostring(column_ifexists('Log',''))) | where Replica == 'salcapa-outdrift-b48224-3tcgdet' or Replica startswith 'salcapa-outdrift-b48224-3tcgdet-' | where Message startswith 'OUTSIDE_COHORT_' or Message startswith 'OUTSIDE_DRIFT_' | project TimeGenerated, Replica, Message | order by TimeGenerated asc | take 101"
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise RecoveryFailure('REDIRECT_DENIED')
def fetch(workspace,token,reference,opener=None):
 need(bool(re.fullmatch('[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}',workspace)),'WORKSPACE_INVALID')
 url='https://api.loganalytics.azure.com/v1/workspaces/'+workspace+'/query?'+urllib.parse.urlencode({'query':query(reference),'timespan':reference['window_start']+'/'+reference['window_end']})
 request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET')
 try:
  with (opener or urllib.request.build_opener(NoRedirect())).open(request,timeout=90) as response:
   need(response.geturl()==url and response.status==200,'LOG_RESPONSE_INVALID');raw=response.read(2097153);need(len(raw)<=2097152,'LOG_RESPONSE_BOUND')
  result=json.loads(raw);need(isinstance(result,dict) and 'error' not in result and len(result.get('tables',[]))==1,'LOG_QUERY_INCOMPLETE')
  table=result['tables'][0];need([c['name'] for c in table['columns']]==['TimeGenerated','Replica','Message'] and len(table['rows'])<=100,'LOG_SCHEMA_OR_ROW_BOUND')
  records=[]
  for row in table['rows']:
   need(len(row)==3 and all(isinstance(v,str) for v in row),'LOG_ROW_INVALID');time,replica,message=row
   need(replica==reference['execution'] or replica.startswith(reference['execution']+'-'),'EXECUTION_MISMATCH')
   clock=datetime.fromisoformat(time.replace('Z','+00:00'));need(datetime.fromisoformat(reference['window_start'].replace('Z','+00:00'))<=clock<=datetime.fromisoformat(reference['window_end'].replace('Z','+00:00')),'LOG_TIME_MISMATCH')
   need(len(message.encode())<=4096 and '\n' not in message and '\r' not in message,'LOG_MESSAGE_BOUND');records.append({'time':time,'message':message})
  return records
 except urllib.error.HTTPError as exc:raise RecoveryFailure('LOG_ACCESS_DENIED' if exc.code in (401,403) else 'LOG_HTTP_FAILURE') from None
 except (urllib.error.URLError,TimeoutError,OSError):raise RecoveryFailure('LOG_READ_FAILURE') from None
def reconstruct(reference,records):
 query(reference)
 # Dual logging routes may duplicate an identical event. Contradictory values are never discarded.
 by_message={};scalars={};rows=[]
 for row in records:
  message=row['message'];need(message.startswith(('OUTSIDE_COHORT_','OUTSIDE_DRIFT_')) and '=' in message,'UNEXPECTED_LOG_MESSAGE')
  by_message.setdefault(message,row)
 for message,row in by_message.items():
  key,value=message.split('=',1)
  if key=='OUTSIDE_COHORT_SOURCE':rows.append(json.loads(value));continue
  need(key in {'OUTSIDE_COHORT_COUNT','OUTSIDE_COHORT_SHA256','OUTSIDE_COHORT_VERIFIED','OUTSIDE_DRIFT_OBSERVED_PHYSICAL_FILES','OUTSIDE_DRIFT_OBSERVED_REPRESENTED_FILES','OUTSIDE_DRIFT_OBSERVED_UNRESOLVED_FILES','OUTSIDE_DRIFT_OBSERVED_OUTSIDE_UNRESOLVED'},'UNEXPECTED_LOG_KEY')
  need(key not in scalars,'CONTRADICTORY_LOG_VALUE');scalars[key]=value
 need(len(rows)==reference['expected_outside_count']==6 and scalars.get('OUTSIDE_COHORT_COUNT')=='6' and scalars.get('OUTSIDE_COHORT_VERIFIED')=='1','SOURCE_BINDINGS_MISSING')
 need(len({row['source_id_sha256'] for row in rows})==6 and bool(re.fullmatch('[a-f0-9]{64}',scalars.get('OUTSIDE_COHORT_SHA256',''))),'SOURCE_BINDINGS_INVALID')
 # Azure may return same-timestamp events out of order. Restore only the order certified by the emitted digest.
 ordered=next((list(p) for p in itertools.permutations(rows) if digest(p)==scalars['OUTSIDE_COHORT_SHA256']),None);need(ordered is not None,'SOURCE_BINDING_DIGEST_MISMATCH')
 source_lookup={json.loads(message.split('=',1)[1])['source_id_sha256']:row for message,row in by_message.items() if message.startswith('OUTSIDE_COHORT_SOURCE=')}
 recovered=[source_lookup[row['source_id_sha256']] for row in ordered]+[row for message,row in by_message.items() if not message.startswith('OUTSIDE_COHORT_SOURCE=')]
 observed={'OUTSIDE_DRIFT_OBSERVED_PHYSICAL_FILES':'23768','OUTSIDE_DRIFT_OBSERVED_REPRESENTED_FILES':'23778','OUTSIDE_DRIFT_OBSERVED_UNRESOLVED_FILES':'8436','OUTSIDE_DRIFT_OBSERVED_OUTSIDE_UNRESOLVED':'6'}
 need(all(scalars.get(k)==v for k,v in observed.items()),'OBSERVATION_MISMATCH')
 lines=[row['time']+' stdout F '+row['message'] for row in reference['console_records']+recovered]
 text='\n'.join(lines)+'\n';need(len(text.encode())<=131072,'REPORT_BOUND');verify_log(text)
 return text,ordered,{'retrieved_rows':len(records),'deduplicated_messages':len(by_message),'source_sha256':scalars['OUTSIDE_COHORT_SHA256'],'message_set_sha256':digest(sorted(by_message))}
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True);args=parser.parse_args()
 try:
  reference=json.loads(Path(REFERENCE).read_text(encoding='utf-8'))
  result=subprocess.run(['az','account','get-access-token','--resource','https://api.loganalytics.io','--query','accessToken','--output','tsv','--only-show-errors'],capture_output=True,text=True,timeout=30)
  need(result.returncode==0 and bool(result.stdout.strip()),'LOG_TOKEN_UNAVAILABLE');token=result.stdout.strip()
  first=fetch(args.workspace,token,reference);text,rows,proof=reconstruct(reference,first)
  second=fetch(args.workspace,token,reference);again,other,readback=reconstruct(reference,second)
  need(rows==other and proof['message_set_sha256']==readback['message_set_sha256'],'HISTORICAL_READBACK_DRIFT')
  for line in text.splitlines():print('RECOVER_OUTSIDE_RECORD='+line,flush=True)
  print('RECOVER_OUTSIDE_SOURCE_COUNT=6',flush=True);print('RECOVER_OUTSIDE_SOURCE_SHA256='+proof['source_sha256'],flush=True)
  print('RECOVER_OUTSIDE_HISTORICAL_READBACKS_EQUAL=1',flush=True);print('RECOVER_OUTSIDE_REPORT_SHA256='+hashlib.sha256(text.encode()).hexdigest(),flush=True)
  print('RECOVER_OUTSIDE_DATABASE_WRITES=0',flush=True);print('RECOVER_OUTSIDE_JOB_STARTS=0',flush=True);print('RECOVER_OUTSIDE_COMPLETE=1',flush=True)
 except Exception as exc:
  code=str(exc) if isinstance(exc,RecoveryFailure) else 'HISTORICAL_LOG_PROOF_INVALID';print('RECOVER_OUTSIDE_FAILURE='+code,flush=True);raise SystemExit(1) from None
if __name__=='__main__':main()
