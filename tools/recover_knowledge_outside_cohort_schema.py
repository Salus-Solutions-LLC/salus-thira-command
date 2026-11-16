"""One bounded metadata GET, then two complete exact-execution historical GETs."""
import argparse,json,re,subprocess,sys,urllib.error,urllib.parse,urllib.request
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import recover_knowledge_outside_cohort_log as base
need=base.need;RecoveryFailure=base.RecoveryFailure
SCHEMAS={'ContainerAppConsoleLogs':{'TimeGenerated':'datetime','ContainerGroupName':'string','Log':'string'},'ContainerAppConsoleLogs_CL':{'TimeGenerated':'datetime','ContainerGroupName_s':'string','Log_s':'string'}}
KNOWN_CODES={'PartialError','BadArgumentError','SemanticError','QueryExecutionError','QueryExecutionError','Forbidden','UnauthorizedError','InsufficientAccessError','AuthorizationFailed','RequestTimeout','TooManyRequests','InternalServerError'}
class Budget:
 def __init__(self):self.reads=0
 def consume(self):self.reads+=1;need(self.reads<=3,'READ_BUDGET')
def safe_code(value):return value if isinstance(value,str) and value in KNOWN_CODES else 'OTHER'
def profile(result,status):
 result=result if isinstance(result,dict) else {};error=result.get('error');tables=result.get('tables')
 shapes=[]
 if isinstance(tables,list):
  for table in tables[:4]:
   if not isinstance(table,dict):continue
   cols=table.get('columns');rows=table.get('rows');name=table.get('name')
   shapes.append({'name':name if name in ('PrimaryResult','QueryStatus') else 'OTHER','column_count':len(cols) if isinstance(cols,list) else -1,'row_count':len(rows) if isinstance(rows,list) else -1,'required_result_columns':isinstance(cols,list) and [c.get('name') for c in cols if isinstance(c,dict)]==['TimeGenerated','Replica','Message']})
 return {'http_status':status,'error_present':error is not None,'error_code':safe_code(error.get('code')) if isinstance(error,dict) else 'NONE' if error is None else 'MALFORMED','inner_code':safe_code(error.get('innererror',{}).get('code')) if isinstance(error,dict) and isinstance(error.get('innererror',{}),dict) else 'NONE','table_count':len(tables) if isinstance(tables,list) else -1,'result_shapes':shapes}
def get_json(workspace,token,endpoint,budget,params=None,opener=None):
 need(bool(re.fullmatch('[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}',workspace)),'WORKSPACE_INVALID');need(endpoint in ('metadata','query'),'ENDPOINT_DENIED')
 need((endpoint=='metadata' and params is None) or (endpoint=='query' and isinstance(params,dict) and set(params)=={'query','timespan'}),'PARAMETERS_DENIED')
 url='https://api.loganalytics.azure.com/v1/workspaces/'+workspace+'/'+endpoint+('?' +urllib.parse.urlencode(params) if params else '')
 request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token,'Accept':'application/json'},method='GET');budget.consume()
 try:
  with (opener or urllib.request.build_opener(base.NoRedirect())).open(request,timeout=90) as response:
   need(response.geturl()==url and response.status==200,'LOG_RESPONSE_INVALID');raw=response.read(2097153);need(len(raw)<=2097152,'LOG_RESPONSE_BOUND')
  result=json.loads(raw);print('SCHEMA_LOG_RECOVERY_RESPONSE='+json.dumps(profile(result,200),sort_keys=True),flush=True)
  need(isinstance(result,dict) and result.get('error') is None,'LOG_QUERY_INCOMPLETE');return result
 except urllib.error.HTTPError as exc:
  print('SCHEMA_LOG_RECOVERY_HTTP_STATUS='+str(exc.code),flush=True)
  try:
   raw=exc.read(16385)
   if len(raw)<=16384:print('SCHEMA_LOG_RECOVERY_RESPONSE='+json.dumps(profile(json.loads(raw),exc.code),sort_keys=True),flush=True)
  except Exception:pass
  raise RecoveryFailure('LOG_ACCESS_DENIED' if exc.code in (401,403) else 'LOG_HTTP_FAILURE') from None
 except (urllib.error.URLError,TimeoutError,OSError):raise RecoveryFailure('LOG_READ_FAILURE') from None
def select_schemas(result):
 tables=result.get('tables');need(isinstance(tables,list) and len(tables)<=2000,'METADATA_SCHEMA_INVALID');selected=[];seen=set();availability={name:False for name in SCHEMAS}
 for table in tables:
  need(isinstance(table,dict),'METADATA_SCHEMA_INVALID');name=table.get('name')
  if name not in SCHEMAS:continue
  need(name not in seen,'DUPLICATE_METADATA_TABLE');seen.add(name);availability[name]=True
  columns=table.get('columns');need(isinstance(columns,list),'METADATA_SCHEMA_INVALID');known={}
  for column in columns:
   if isinstance(column,dict) and column.get('name') in SCHEMAS[name]:
    need(column['name'] not in known,'DUPLICATE_METADATA_COLUMN');known[column['name']]=str(column.get('type','')).lower()
  print('SCHEMA_LOG_RECOVERY_REQUIRED_COLUMNS='+json.dumps({'table':name,'columns':{k:known.get(k,'MISSING') if known.get(k,'MISSING') in ('datetime','string','MISSING') else 'OTHER' for k in SCHEMAS[name]}},sort_keys=True),flush=True)
  need(known==SCHEMAS[name],'KNOWN_SCHEMA_COLUMNS_INVALID');selected.append(name)
 print('SCHEMA_LOG_RECOVERY_KNOWN_TABLES='+json.dumps(availability,sort_keys=True),flush=True);need(bool(selected),'KNOWN_LOG_SCHEMAS_UNAVAILABLE');return tuple(sorted(selected))
def query(reference,tables):
 original=base.query(reference);need(bool(tables) and len(tables)==len(set(tables)) and set(tables)<=set(SCHEMAS),'TABLE_SCOPE_DENIED')
 return (tables[0] if len(tables)==1 else 'union '+', '.join(tables))+' | '+original.split(' | ',1)[1]
def fetch(workspace,token,reference,tables,budget,opener=None):
 result=get_json(workspace,token,'query',budget,{'query':query(reference,tables),'timespan':reference['window_start']+'/'+reference['window_end']},opener)
 need(isinstance(result.get('tables'),list) and len(result['tables'])==1,'LOG_RESULT_TABLE_COUNT');table=result['tables'][0]
 need([c['name'] for c in table['columns']]==['TimeGenerated','Replica','Message'] and len(table['rows'])<=100,'LOG_SCHEMA_OR_ROW_BOUND');records=[]
 for row in table['rows']:
  need(len(row)==3 and all(isinstance(v,str) for v in row),'LOG_ROW_INVALID');time,replica,message=row
  need(replica==reference['execution'] or replica.startswith(reference['execution']+'-'),'EXECUTION_MISMATCH');clock=datetime.fromisoformat(time.replace('Z','+00:00'))
  need(datetime.fromisoformat(reference['window_start'].replace('Z','+00:00'))<=clock<=datetime.fromisoformat(reference['window_end'].replace('Z','+00:00')),'LOG_TIME_MISMATCH')
  need(len(message.encode())<=4096 and '\n' not in message and '\r' not in message,'LOG_MESSAGE_BOUND');records.append({'time':time,'message':message})
 return records
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--workspace',required=True);args=parser.parse_args()
 try:
  reference=json.loads(Path(base.REFERENCE).read_text(encoding='utf-8'));base.query(reference)
  result=subprocess.run(['az','account','get-access-token','--resource','https://api.loganalytics.io','--query','accessToken','--output','tsv','--only-show-errors'],capture_output=True,text=True,timeout=30)
  need(result.returncode==0 and bool(result.stdout.strip()),'LOG_TOKEN_UNAVAILABLE');token=result.stdout.strip();budget=Budget()
  tables=select_schemas(get_json(args.workspace,token,'metadata',budget))
  first=fetch(args.workspace,token,reference,tables,budget);text,rows,proof=base.reconstruct(reference,first)
  second=fetch(args.workspace,token,reference,tables,budget);again,other,readback=base.reconstruct(reference,second)
  need(rows==other and proof['message_set_sha256']==readback['message_set_sha256'],'HISTORICAL_READBACK_DRIFT')
  for line in text.splitlines():print('RECOVER_OUTSIDE_RECORD='+line,flush=True)
  print('RECOVER_OUTSIDE_SOURCE_COUNT=6',flush=True);print('RECOVER_OUTSIDE_SOURCE_SHA256='+proof['source_sha256'],flush=True)
  print('RECOVER_OUTSIDE_HISTORICAL_READBACKS_EQUAL=1',flush=True);print('RECOVER_OUTSIDE_REPORT_SHA256='+base.hashlib.sha256(text.encode()).hexdigest(),flush=True)
  print('SCHEMA_LOG_RECOVERY_GET_READS='+str(budget.reads),flush=True);print('RECOVER_OUTSIDE_DATABASE_WRITES=0',flush=True);print('RECOVER_OUTSIDE_JOB_STARTS=0',flush=True);print('RECOVER_OUTSIDE_COMPLETE=1',flush=True)
 except Exception as exc:
  print('SCHEMA_LOG_RECOVERY_FAILURE='+(str(exc) if isinstance(exc,RecoveryFailure) else 'HISTORICAL_LOG_PROOF_INVALID'),flush=True);raise SystemExit(1) from None
if __name__=='__main__':main()
