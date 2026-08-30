#!/usr/bin/env python3
from datetime import datetime,timedelta,timezone
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
def main():
 spec=importlib.util.spec_from_file_location('ci_v16',ROOT/'tools'/'ci_v16_smoke.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);actual=app.APP_VERSION
 try: app.APP_VERSION='1.6.0';m.main()
 finally: app.APP_VERSION=actual
 client=TestClient(app.app);h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V17 CI','X-Salus-Tenant':'1'};p={'name':'V17 Lifecycle Assessment','organization':'Salus','assessment_type':'Enterprise','purpose':'Lifecycle smoke','mission':'Validate reassessment governance','scope':'CI','reassessment_date':'2000-01-01'}
 r=client.post('/api/assessments',headers=h,json=p);assert r.status_code==200,r.text;aid=r.json()['id'];a=next(x for x in client.get('/api/assessments',headers=h).json() if x['id']==aid);assert a['reassessment_lifecycle_status']=='Reassessment Overdue'
 tr=lambda:[x for x in client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json() if x['source']=='Assessment Lifecycle'];assert len(tr())==1 and tr()[0]['status']=='Open';client.get('/api/dashboard',headers=h);assert len(tr())==1;assert client.put(f'/api/assessments/{aid}',headers=h,json={'reassessment_date':'2099-01-01'}).status_code==409
 next_date=(datetime.now(timezone.utc).date()+timedelta(days=365)).isoformat();rr=client.post(f'/api/assessments/{aid}/reassessment-review',headers=h,json={'next_reassessment_date':next_date,'review_outcome':'Scope, threats, capabilities, and decisions reviewed.'});assert rr.status_code==200,rr.text;assert rr.json()['reassessment_lifecycle_status']=='Current' and rr.json()['last_reassessment_review_by']=='V17 CI' and tr()[0]['status']=='Resolved';assert client.get('/health/ready').json()['version']=='1.7.0';print('V1_7_ASSESSMENT_REASSESSMENT_PASS',app.DB_BACKEND)
if __name__=='__main__':main()
