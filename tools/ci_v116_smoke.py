#!/usr/bin/env python3
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND','sqlite')
os.environ.setdefault('SALUS_DB_PATH',str(Path(TMP.name)/'v116-smoke.db'))
os.environ.setdefault('SALUS_AUTH_MODE','prototype')
sys.path.insert(0,str(ROOT))

from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def post(client,path,headers,payload,status=200):
    response=client.post(path,headers=headers,json=payload)
    assert response.status_code==status,(path,response.status_code,response.text)
    return response.json() if response.content else None


def main():
    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V116 Assessor','X-Salus-Tenant':'1','X-Salus-Clearance':'Highly Sensitive'}
    authority={**h,'X-Salus-Role':'Client Executive','X-Salus-User':'Protected Member Executive'}
    aid=post(client,'/api/assessments',h,{'name':'V116 Executive Governance','organization':'Member Client Alpha'})['id']
    other_aid=post(client,'/api/assessments',h,{'name':'V116 Boundary','organization':'Member Client Alpha'})['id']
    threat=post(client,'/api/threats',h,{'assessment_id':aid,'name':'Continuity disruption','category':'Operational'})
    scenario=post(client,'/api/scenarios',h,{'assessment_id':aid,'threat_id':threat['id'],'title':'Extended disruption','narrative':'A material disruption requires an accountable decision.'})
    capability=post(client,'/api/capabilities',h,{'assessment_id':aid,'scenario_id':scenario['id'],'name':'Continuity','required_outcome':'Restore priority services.','required_standard':95,'current_performance':60})
    gap=post(client,'/api/gaps',h,{'assessment_id':aid,'capability_id':capability['id'],'description':'Demonstrated continuity remains below target.','severity':'High'})
    improvement=post(client,'/api/improvements',h,{'assessment_id':aid,'gap_id':gap['id'],'title':'Add an independent recovery path','owner':'Continuity Program Owner'})
    other_capability=post(client,'/api/capabilities',h,{'assessment_id':other_aid,'name':'Boundary capability','required_outcome':'Remain isolated.','required_standard':100,'current_performance':50})
    other_gap=post(client,'/api/gaps',h,{'assessment_id':other_aid,'capability_id':other_capability['id'],'description':'Boundary gap.'})
    other_improvement=post(client,'/api/improvements',h,{'assessment_id':other_aid,'gap_id':other_gap['id'],'title':'Boundary improvement'})
    future=(date.today()+timedelta(days=180)).isoformat()

    base={'assessment_id':aid,'improvement_id':improvement['id'],'decision_type':'Accept Risk','authority':'Chief Operating Officer','rationale':'Residual exposure is accepted while the recovery path is implemented.','funding_authorized':25000,'conditions':'Reconsider after an incident, material threat change, or failed recovery exercise.','implementation_owner':'Continuity Executive','target_completion':future,'expected_residual_risk':'Moderate continuity exposure remains during implementation.','review_date':future}
    for key,value in {'review_lifecycle_status':'Current','created_at':'2000-01-01T00:00:00Z','tenant_id':2,'decision_type':'Invented Decision','funding_authorized':-1}.items():
        response=client.post('/api/decisions',headers=authority,json={**base,key:value})
        assert response.status_code==422,(key,response.text)
    for missing in ('authority','rationale','conditions','implementation_owner','expected_residual_risk','review_date'):
        response=client.post('/api/decisions',headers=authority,json={**base,missing:''})
        assert response.status_code==422,(missing,response.text)
    assert client.post('/api/decisions',headers=authority,json={**base,'review_date':(date.today()-timedelta(days=1)).isoformat()}).status_code==422
    assert client.post('/api/decisions',headers=authority,json={**base,'improvement_id':other_improvement['id']}).status_code==422

    # A forced accepted-risk insertion failure must roll back the decision as well.
    real_db=app.db
    class FailingAcceptedRiskConnection:
        def __init__(self,inner): self.inner=inner
        def execute(self,sql,params=()):
            if 'INSERT INTO accepted_risks' in sql: raise RuntimeError('forced accepted-risk insertion failure')
            return self.inner.execute(sql,params)
        def __getattr__(self,name): return getattr(self.inner,name)
    conn=real_db(); before=conn.execute("SELECT COUNT(*) c FROM decisions WHERE rationale=?",('Atomic rollback marker.',)).fetchone()['c']; conn.close()
    app.db=lambda:FailingAcceptedRiskConnection(real_db())
    try:
        atomic_client=TestClient(app.app,raise_server_exceptions=False)
        failed=atomic_client.post('/api/decisions',headers=authority,json={**base,'rationale':'Atomic rollback marker.'})
        assert failed.status_code==500,failed.text
    finally:
        app.db=real_db
    conn=app.db(); after=conn.execute("SELECT COUNT(*) c FROM decisions WHERE rationale=?",('Atomic rollback marker.',)).fetchone()['c']; conn.close()
    assert before==after==0

    decision=post(client,'/api/decisions',authority,base)
    decisions=client.get(f'/api/decisions?assessment_id={aid}',headers=h).json()
    accepted=client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h).json()
    risk=next(x for x in accepted if x['decision_id']==decision['id'])
    assert len([x for x in decisions if x['id']==decision['id']])==1
    assert risk['status']=='Active' and risk['owner']=='Continuity Executive' and risk['review_lifecycle_status']=='Current'
    assert client.put(f'/api/decisions/{decision["id"]}',headers=h,json={'authority':'Forged'}).status_code==404
    for forged in ({'status':'Closed'},{'closure_basis':'Forged basis.'},{'authority':'Forged authority.'},{'review_date':future},{'review_lifecycle_status':'Current'}):
        response=client.put(f'/api/accepted_risks/{risk["id"]}',headers=h,json=forged)
        assert response.status_code==409,(forged,response.text)
    updated=client.put(f'/api/accepted_risks/{risk["id"]}',headers=h,json={'owner':'Deputy Continuity Executive','reconsideration_trigger':'Reconsider on any failed recovery exercise.'})
    assert updated.status_code==200 and updated.json()['owner']=='Deputy Continuity Executive'

    yesterday=(date.today()-timedelta(days=1)).isoformat()
    conn=app.db()
    conn.execute("UPDATE decisions SET review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='' WHERE id=?",(yesterday,decision['id']))
    conn.execute("UPDATE accepted_risks SET review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='' WHERE id=?",(yesterday,risk['id']))
    conn.commit(); conn.close()
    client.get(f'/api/decisions?assessment_id={aid}',headers=h)
    client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h)
    client.get(f'/api/decisions?assessment_id={aid}',headers=h)
    client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h)
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    decision_triggers=[x for x in triggers if x['source']=='Decision Lifecycle' and x['affected_record_id']==decision['id']]
    risk_triggers=[x for x in triggers if x['source']=='Accepted Risk Lifecycle' and x['affected_record_id']==risk['id']]
    assert len(decision_triggers)==1 and decision_triggers[0]['status']=='Open'
    assert len(risk_triggers)==1 and risk_triggers[0]['status']=='Open'

    reviewed_decision=post(client,f'/api/decisions/{decision["id"]}/review',authority,{'next_review_date':future,'review_outcome':'The executive decision remains appropriate within the documented conditions.'})
    assert reviewed_decision['review_lifecycle_status']=='Current' and reviewed_decision['last_review_by']=='Protected Member Executive'
    reviewed_risk=post(client,f'/api/accepted-risks/{risk["id"]}/review',authority,{'next_review_date':future,'review_outcome':'The authority confirmed continued acceptance within tolerance.'})
    assert reviewed_risk['review_lifecycle_status']=='Current' and reviewed_risk['last_review_by']=='Protected Member Executive'
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    assert next(x for x in triggers if x['id']==decision_triggers[0]['id'])['status']=='Resolved'
    assert next(x for x in triggers if x['id']==risk_triggers[0]['id'])['status']=='Resolved'

    under_review=post(client,f'/api/accepted-risks/{risk["id"]}/transition',authority,{'status':'Under Review','reason':'The accountable authority opened a focused acceptance review.'})
    assert under_review['status']=='Under Review'
    assert post(client,f'/api/accepted-risks/{risk["id"]}/transition',authority,{'status':'Active','reason':'Attempt to bypass controlled review.'},422)
    active=post(client,f'/api/accepted-risks/{risk["id"]}/review',authority,{'next_review_date':future,'review_outcome':'The focused review confirmed continued acceptance.'})
    assert active['status']=='Active'
    conn=app.db(); conn.execute("UPDATE accepted_risks SET review_date=?,review_lifecycle_status='Current',review_overdue_reason='',review_overdue_at='' WHERE id=?",(yesterday,risk['id'])); conn.commit(); conn.close()
    client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h)
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    second_episode=[x for x in triggers if x['source']=='Accepted Risk Lifecycle' and x['affected_record_id']==risk['id']]
    assert len(second_episode)==2 and len([x for x in second_episode if x['status']=='Open'])==1
    closed=post(client,f'/api/accepted-risks/{risk["id"]}/transition',authority,{'status':'Closed','reason':'Independent recovery testing removed the accepted residual exposure.'})
    assert closed['status']=='Closed' and closed['closure_basis']
    assert post(client,f'/api/accepted-risks/{risk["id"]}/transition',authority,{'status':'Under Review','reason':'Attempt to reopen terminal history.'},409)
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    assert all(x['status']=='Resolved' for x in triggers if x['source']=='Accepted Risk Lifecycle' and x['affected_record_id']==risk['id'])

    exported=client.get(f'/api/export/{aid}',headers=h).json()
    assert any(x['id']==decision['id'] for x in exported['decisions'])
    assert any(x['id']==risk['id'] and x['status']=='Closed' for x in exported['accepted_risks'])
    assert 'Accepted Risk Register' in client.get(f'/api/report/{aid}/executive.html',headers=h).text
    assert 'Executive Decisions' in client.get(f'/api/report/{aid}/executive.csv',headers=h).text
    conn=app.db()
    audits=[dict(x) for x in conn.execute("SELECT * FROM audit_log WHERE entity_type IN ('decision','accepted_risk') AND entity_id IN (?,?) ORDER BY id",(decision['id'],risk['id']))]
    decision_versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='decisions' AND entity_id=? ORDER BY version_no",(decision['id'],))]
    risk_versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='accepted_risks' AND entity_id=? ORDER BY version_no",(risk['id'],))]
    package=collect_tenant_records(conn,1); conn.close()
    actions={x['action'] for x in audits}
    assert {'CREATE','DECISION_REVIEW_OVERDUE','DECISION_REVIEW','ACCEPTED_RISK_REVIEW_OVERDUE','ACCEPTED_RISK_REVIEW','ACCEPTED_RISK_TRANSITION'} <= actions
    assert len(decision_versions)>=3 and len(risk_versions)>=8
    assert any(x['id']==decision['id'] for x in package['decisions'])
    assert any(x['id']==risk['id'] and x['status']=='Closed' for x in package['accepted_risks'])
    assert client.get('/health/ready').json()['version']=='1.16.0'
    print('V1_16_EXECUTIVE_DECISION_ACCEPTED_RISK_PASS',app.DB_BACKEND)


if __name__=='__main__': main()
