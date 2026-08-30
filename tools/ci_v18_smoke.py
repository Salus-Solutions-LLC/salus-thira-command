#!/usr/bin/env python3
from datetime import datetime,timedelta,timezone
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
def main():
 spec=importlib.util.spec_from_file_location('ci_v17',ROOT/'tools'/'ci_v17_smoke.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);actual=app.APP_VERSION
 try: app.APP_VERSION='1.7.0';m.main()
 finally: app.APP_VERSION=actual
 client=TestClient(app.app);h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V18 CI','X-Salus-Tenant':'1'}
 aid=client.post('/api/assessments',headers=h,json={'name':'V18 Decision Lifecycle','organization':'Salus','assessment_type':'Enterprise','purpose':'Lifecycle smoke','mission':'Validate decision review governance','scope':'CI'}).json()['id']
 future=(datetime.now(timezone.utc).date()+timedelta(days=30)).isoformat();r=client.post('/api/decisions',headers=h,json={'assessment_id':aid,'decision_type':'Continue Monitoring','authority':'V18 Authority','rationale':'Governed monitoring decision','review_date':future});assert r.status_code==200,r.text;did=r.json()['id']
 conn=app.db();conn.execute("UPDATE decisions SET review_date='2000-01-01' WHERE id=?",(did,));conn.commit();conn.close()
 decisions=client.get(f'/api/decisions?assessment_id={aid}',headers=h).json();d=next(x for x in decisions if x['id']==did);assert d['review_lifecycle_status']=='Review Overdue'
 tr=lambda:[x for x in client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json() if x['source']=='Decision Lifecycle' and x['affected_record_id']==did]
 assert len(tr())==1 and tr()[0]['status']=='Open';client.get('/api/dashboard',headers=h);assert len(tr())==1
 assert client.put(f'/api/decisions/{did}',headers=h,json={'review_date':future}).status_code in (404,405)
 next_date=(datetime.now(timezone.utc).date()+timedelta(days=365)).isoformat();rr=client.post(f'/api/decisions/{did}/review',headers=h,json={'next_review_date':next_date,'review_outcome':'Authority reviewed the decision and confirmed continued monitoring.'});assert rr.status_code==200,rr.text
 assert rr.json()['review_lifecycle_status']=='Current' and rr.json()['last_review_by']=='V18 CI' and tr()[0]['status']=='Resolved'
 versions=client.get(f'/api/entity_versions?assessment_id={aid}',headers=h).json();assert len([x for x in versions if x['entity_type']=='decisions' and x['entity_id']==did])>=3
 assert client.get('/health/ready').json()['version']=='1.8.0';print('V1_8_EXECUTIVE_DECISION_REVIEW_PASS',app.DB_BACKEND)
if __name__=='__main__':main()
