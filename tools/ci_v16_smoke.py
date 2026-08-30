#!/usr/bin/env python3
"""Professional risk-override review lifecycle smoke shared by SQLite/PostgreSQL CI."""
from datetime import datetime,timedelta,timezone
import importlib.util,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app

def run_v15_regression():
    spec=importlib.util.spec_from_file_location('ci_v15',ROOT/'tools'/'ci_v15_smoke.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    actual=app.APP_VERSION
    try: app.APP_VERSION='1.5.0'; module.main()
    finally: app.APP_VERSION=actual

def main():
    run_v15_regression(); client=TestClient(app.app); h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V16 CI','X-Salus-Tenant':'1'}
    c=app.db(); aid=c.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']; tid=c.execute('SELECT id FROM threats WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']; c.close()
    future=(datetime.now(timezone.utc).date()+timedelta(days=30)).isoformat(); payload={'assessment_id':aid,'threat_id':tid,'assigned_score':77,'reason':'Professional judgment identifies concentration risk.','authority':'CI Executive','review_date':future}
    response=client.post('/api/risk-overrides',headers=h,json=payload); assert response.status_code==200,response.text; oid=response.json()['id']
    legacy=client.post('/api/risk-overrides',headers=h,json=payload|{'threat_id':tid,'assigned_score':76,'review_date':''}); assert legacy.status_code==200,legacy.text; assert legacy.json()['review_date']>datetime.now(timezone.utc).date().isoformat(); oid=legacy.json()['id']
    assert client.post('/api/risk-overrides',headers=h,json=payload|{'review_date':'2000-01-01'}).status_code==422
    c=app.db(); c.execute("UPDATE risk_overrides SET review_date='2000-01-01' WHERE id=?",(oid,)); c.commit(); c.close()
    modeled=next(x for x in client.get(f'/api/risk/{aid}',headers=h).json() if x['threat_id']==tid); assert modeled['professional_override'] is None and modeled['assigned_risk_score'] is None
    row=next(x for x in client.get(f'/api/risk_overrides?assessment_id={aid}',headers=h).json() if x['id']==oid); assert row['review_lifecycle_status']=='Review Overdue' and row['review_overdue_at']
    triggers=lambda:[x for x in client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json() if x['affected_record_type']=='risk_override' and x['affected_record_id']==oid]
    assert len(triggers())==1 and triggers()[0]['status']=='Open'; client.get(f'/api/risk/{aid}',headers=h); assert len(triggers())==1
    next_review=(datetime.now(timezone.utc).date()+timedelta(days=365)).isoformat(); reviewed=client.post(f'/api/risk-overrides/{oid}/review',headers=h,json={'next_review_date':next_review,'review_outcome':'Authority reconfirmed the professional assignment.'}); assert reviewed.status_code==200,reviewed.text
    assert reviewed.json()['review_lifecycle_status']=='Current' and reviewed.json()['last_review_by']=='V16 CI' and triggers()[0]['status']=='Resolved'
    modeled=next(x for x in client.get(f'/api/risk/{aid}',headers=h).json() if x['threat_id']==tid); assert modeled['professional_override']['id']==oid and modeled['assigned_risk_score']==76
    c=app.db(); assert c.execute("SELECT COUNT(*) c FROM audit_log WHERE entity_type='risk_override' AND entity_id=? AND action IN ('RISK_OVERRIDE_REVIEW_OVERDUE','RISK_OVERRIDE_REVIEW')",(oid,)).fetchone()['c']==2; assert c.execute("SELECT COUNT(*) c FROM entity_versions WHERE entity_type='risk_overrides' AND entity_id=?",(oid,)).fetchone()['c']>=3; c.close()
    assert client.get('/health/ready').json()['version']=='1.6.0'; print('V1_6_RISK_OVERRIDE_REVIEW_PASS',app.DB_BACKEND)

if __name__=='__main__': main()
