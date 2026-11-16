"""Bounded ARM GET transport only; never submits or repeats a start/deployment."""
import argparse,json,math,re,subprocess,sys,time
from datetime import datetime,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,parse_qs
from urllib.request import Request,build_opener,HTTPRedirectHandler

class TransportFailure(Exception):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def validate_url(url):
 p=urlsplit(url)
 if p.scheme!='https' or p.netloc!='management.azure.com' or p.fragment or p.username or p.password:raise TransportFailure('ARM_URL_DENIED')
 if not re.fullmatch(r'/subscriptions/[0-9a-fA-F-]{36}/resourceGroups/rg-salcapa-dev/providers/(Microsoft\.App|Microsoft\.Resources)/[A-Za-z0-9_./-]+',p.path,re.IGNORECASE) or '..' in p.path:raise TransportFailure('ARM_SCOPE_DENIED')
 q=parse_qs(p.query,strict_parsing=True,keep_blank_values=True)
 if 'api-version' not in q or set(q)-{'api-version','$skiptoken'} or q['api-version'] not in (['2025-07-01'],['2026-07-01'],['2022-09-01']):raise TransportFailure('ARM_QUERY_DENIED')
 if '$skiptoken' in q and (not p.path.lower().endswith('/microsoft.app/jobs') or len(q['$skiptoken'])!=1 or not q['$skiptoken'][0]):raise TransportFailure('ARM_QUERY_DENIED')
 return url

def access_token():
 p=subprocess.run(['az','account','get-access-token','--resource','https://management.azure.com/','--output','json','--only-show-errors'],capture_output=True,text=True,timeout=30)
 if p.returncode:raise TransportFailure('ARM_TOKEN_UNAVAILABLE')
 try:token=json.loads(p.stdout)['accessToken']
 except (ValueError,KeyError,TypeError):raise TransportFailure('ARM_TOKEN_UNAVAILABLE') from None
 if not isinstance(token,str) or not token:raise TransportFailure('ARM_TOKEN_UNAVAILABLE')
 return token

def retry_delay(value,attempt,wall_clock=lambda:datetime.now(timezone.utc)):
 fallback=min(5*(2**attempt),60)
 if not value:return fallback
 try:delay=float(value)
 except ValueError:
  try:delay=(parsedate_to_datetime(value)-wall_clock()).total_seconds()
  except (ValueError,TypeError,OverflowError):raise TransportFailure('ARM_RETRY_AFTER_INVALID') from None
 if not math.isfinite(delay):raise TransportFailure('ARM_RETRY_AFTER_INVALID')
 if delay<0:delay=0
 return max(fallback,delay)

class ArmReader:
 def __init__(self,token,*,opener=None,clock=time.monotonic,sleep=time.sleep):self.token=token;self.opener=opener or build_opener(NoRedirect());self.clock=clock;self.sleep=sleep
 def get(self,url,*,deadline=None,allow_missing=False):
  validate_url(url);deadline=min(deadline if deadline is not None else self.clock()+120,self.clock()+120)
  for attempt in range(5):
   remaining=deadline-self.clock()
   if remaining<=0:raise TransportFailure('ARM_READ_BUDGET')
   request=Request(url,headers={'Authorization':'Bearer '+self.token,'Accept':'application/json'},method='GET')
   try:
    with self.opener.open(request,timeout=min(30,remaining)) as response:
     if response.status!=200:raise TransportFailure('ARM_UNEXPECTED_STATUS')
     raw=response.read(8*1024*1024+1)
     if self.clock()>deadline:raise TransportFailure('ARM_READ_BUDGET')
     if len(raw)>8*1024*1024:raise TransportFailure('ARM_RESPONSE_BOUND')
     return json.loads(raw)
   except HTTPError as exc:
    if exc.code==404 and allow_missing:return None
    if exc.code not in (429,500,502,503,504):raise TransportFailure('ARM_HTTP_'+str(exc.code)) from None
    if attempt==4:raise TransportFailure('ARM_READ_RETRY_LIMIT') from None
    delay=retry_delay(exc.headers.get('Retry-After'),attempt)
   except (URLError,TimeoutError):
    if attempt==4:raise TransportFailure('ARM_NETWORK_RETRY_LIMIT') from None
    delay=retry_delay(None,attempt)
   if delay>=deadline-self.clock():raise TransportFailure('ARM_RETRY_DEFERRED')
   print('INVENTORY_RECOVERY_ARM_GET_RETRY='+str(attempt+1),flush=True);print('INVENTORY_RECOVERY_ARM_DELAY_SECONDS='+str(delay),flush=True);self.sleep(delay)
  raise TransportFailure('ARM_READ_RETRY_LIMIT')

def wait(reader,url,*,kind,seconds,output,clock=time.monotonic,sleep=time.sleep):
 if kind not in ('deployment','execution') or not 1<=seconds<=960:raise TransportFailure('ARM_WAIT_SCOPE')
 deadline=clock()+seconds
 while clock()<deadline:
  result=reader.get(url,deadline=deadline,allow_missing=True)
  if result is None:status='NotFound'
  else:
   Path(output).write_text(json.dumps(result),encoding='utf-8');status=(result.get('properties') or {}).get('provisioningState' if kind=='deployment' else 'status','Unknown')
  allowed={'Succeeded','Failed','Canceled','Cancelled','Stopped','Running','Pending','Processing','Accepted','Creating','Updating','NotFound','Unknown'}
  if status not in allowed:raise TransportFailure('ARM_STATE_UNKNOWN')
  print('INVENTORY_RECOVERY_'+kind.upper()+'_STATUS='+status,flush=True)
  if status=='Succeeded':return
  if status in ('Failed','Canceled','Cancelled','Stopped'):raise TransportFailure('ARM_'+kind.upper()+'_FAILED')
  delay=min(15,deadline-clock())
  if delay>0:sleep(delay)
 raise TransportFailure('ARM_'+kind.upper()+'_TIMEOUT')

def discover(reader,url):
 result=reader.get(url,allow_missing=True)
 if result is None:return None
 if result.get('nextLink'):raise TransportFailure('ARM_EXECUTION_LIST_BOUND')
 rows=result.get('value');
 if not isinstance(rows,list) or len(rows)>1:raise TransportFailure('ARM_EXECUTION_AMBIGUOUS')
 if not rows:return None
 name=rows[0].get('name','')
 if not re.fullmatch('[a-z0-9][a-z0-9-]{0,127}',name):raise TransportFailure('ARM_EXECUTION_NAME_INVALID')
 return name

def verify_absence(reader,url,name):
 if not re.fullmatch('[a-z0-9][a-z0-9-]{0,127}',name):raise TransportFailure('ARM_NAMESPACE_NAME_INVALID')
 origin=urlsplit(validate_url(url)).path.lower();seen=set()
 if not origin.endswith('/microsoft.app/jobs'):raise TransportFailure('ARM_NAMESPACE_SCOPE')
 for _ in range(20):
  if url in seen or urlsplit(validate_url(url)).path.lower()!=origin:raise TransportFailure('ARM_NAMESPACE_SCOPE')
  seen.add(url);result=reader.get(url);rows=result.get('value')
  if not isinstance(rows,list) or len(rows)>2000:raise TransportFailure('ARM_NAMESPACE_BOUND')
  if any(str(r.get('name','')).casefold()==name for r in rows):raise TransportFailure('ARM_NAMESPACE_NOT_EMPTY')
  url=result.get('nextLink')
  if not url:return
 raise TransportFailure('ARM_NAMESPACE_PAGE_BOUND')

def main():
 p=argparse.ArgumentParser();p.add_argument('mode',choices=('get','wait-deployment','wait-execution','discover','absent'));p.add_argument('--url',required=True);p.add_argument('--output');p.add_argument('--seconds',type=int,default=120);p.add_argument('--allow-missing',action='store_true');p.add_argument('--name');a=p.parse_args()
 try:
  started=time.monotonic();validate_url(a.url);reader=ArmReader(access_token())
  if a.mode=='get':
   if not a.output:raise TransportFailure('ARM_OUTPUT_REQUIRED')
   Path(a.output).write_text(json.dumps(reader.get(a.url,allow_missing=a.allow_missing)),encoding='utf-8')
  elif a.mode=='absent':
   verify_absence(reader,a.url,a.name or '');print('INVENTORY_RECOVERY_NAMESPACE_ABSENCE_VERIFIED=1')
  elif a.mode=='discover':
   name=discover(reader,a.url)
   if name:
    if a.output:Path(a.output).write_text(name,encoding='utf-8')
    else:print(name)
   else:raise TransportFailure('ARM_EXECUTION_NOT_OBSERVED')
  else:
   if not a.output:raise TransportFailure('ARM_OUTPUT_REQUIRED')
   remaining=a.seconds-int(time.monotonic()-started)
   if remaining<1:raise TransportFailure('ARM_WAIT_BUDGET')
   wait(reader,a.url,kind=a.mode[5:],seconds=remaining,output=a.output)
 except Exception as exc:
  code=str(exc) if isinstance(exc,TransportFailure) else 'ARM_TRANSPORT_UNEXPECTED'
  print('INVENTORY_RECOVERY_TRANSPORT_FAILURE='+code,file=sys.stderr,flush=True);raise SystemExit(1) from None

if __name__=='__main__':main()
