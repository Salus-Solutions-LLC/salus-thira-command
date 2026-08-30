#!/usr/bin/env python3
"""Accepted-risk review lifecycle release smoke shared by SQLite/PostgreSQL CI."""
from datetime import datetime, timedelta, timezone
import base64, gzip
import sys
from pathlib import Path
from starlette.testclient import TestClient
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import app

def run_v141_regression():
    payload=ROOT/'source_archives'/'v1.4.1'/'ci_v141_smoke.py.gz.b64'
    code=compile(gzip.decompress(base64.b64decode(payload.read_text(),validate=True)),str(payload)+'::ci_v141_smoke.py','exec')
    actual=app.APP_VERSION
    try:
        app.APP_VERSION='1.4.1'
        exec(code,{'__name__':'__main__','__file__':str(ROOT/'tools'/'ci_v141_smoke.py')})
    finally:
        app.APP_VERSION=actual

def main():
    run_v141_regression()
    client=TestClient(app.app); h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V15 CI','X-Salus-Tenant':'1'}
    c=app.db(); aid=c.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']; c.close()
    decision={'assessment_id':aid,'decision_type':'Accept Risk','authority':'CI Executive','rationale':'Governed acceptance remains necessary.','conditions':'Reconsider on material change.','implementation_owner':'CI Risk Owner','expected_residual_risk':'Moderate residual exposure remains.','review_date':'2000-01-01'}
    response=client.post('/api/decisions',headers=h,json=decision); assert response.status_code==200,response.text
    risk=next(x for x in client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h).json() if x['decision_id']==response.json()['id'])
    assert risk['status']=='Active' and risk['review_lifecycle_status']=='Review Overdue' and risk['review_overdue_at']
    triggers=lambda:[x for x in client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json() if x['source']=='Accepted Risk Lifecycle' and x['affected_record_id']==risk['id']]
    assert len(triggers())==1 and triggers()[0]['status']=='Open'
    client.get('/api/dashboard',headers=h); client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h); assert len(triggers())==1
    for payload in ({'review_date':'2099-01-01'},{'review_lifecycle_status':'Current'},{'review_overdue_at':''}):
        blocked=client.put(f"/api/accepted_risks/{risk['id']}",headers=h,json=payload); assert blocked.status_code==409,blocked.text
    assert client.post(f"/api/accepted-risks/{risk['id']}/review",headers=h,json={'next_review_date':'2000-02-01','review_outcome':'Invalid renewal'}).status_code==422
    next_review=(datetime.now(timezone.utc).date()+timedelta(days=365)).isoformat()
    reviewed=client.post(f"/api/accepted-risks/{risk['id']}/review",headers=h,json={'next_review_date':next_review,'review_outcome':'Authority confirmed continued acceptance within tolerance.'}); assert reviewed.status_code==200,reviewed.text
    renewed=reviewed.json(); assert renewed['review_lifecycle_status']=='Current' and renewed['review_date']==next_review and renewed['last_review_by']=='V15 CI' and not renewed['review_overdue_at']
    assert len(triggers())==1 and triggers()[0]['status']=='Resolved'
    c=app.db()
    assert c.execute("SELECT COUNT(*) c FROM audit_log WHERE entity_type='accepted_risk' AND entity_id=? AND action IN ('ACCEPTED_RISK_REVIEW_OVERDUE','ACCEPTED_RISK_REVIEW')",(risk['id'],)).fetchone()['c']==2
    assert c.execute("SELECT COUNT(*) c FROM entity_versions WHERE entity_type='accepted_risks' AND entity_id=?",(risk['id'],)).fetchone()['c']>=3
    c.close(); print('V1_5_ACCEPTED_RISK_LIFECYCLE_PASS',app.DB_BACKEND)

if __name__=='__main__': main()
