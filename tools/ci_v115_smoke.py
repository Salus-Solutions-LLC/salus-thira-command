#!/usr/bin/env python3
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND','sqlite')
os.environ.setdefault('SALUS_DB_PATH',str(Path(TMP.name)/'v115-smoke.db'))
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
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V115 Authority','X-Salus-Tenant':'1','X-Salus-Clearance':'Highly Sensitive'}
    aid=post(client,'/api/assessments',h,{'name':'V115 Operational Risk','organization':'Member Client Alpha'})['id']
    other_aid=post(client,'/api/assessments',h,{'name':'V115 Boundary','organization':'Member Client Alpha'})['id']
    threat=post(client,'/api/threats',h,{'assessment_id':aid,'name':'Sustained service disruption','category':'Operational','likelihood':5,'vulnerability':4,'consequence':5})
    other_threat=post(client,'/api/threats',h,{'assessment_id':other_aid,'name':'Boundary threat','category':'Operational'})
    scenario=post(client,'/api/scenarios',h,{'assessment_id':aid,'threat_id':threat['id'],'title':'Extended outage','narrative':'A sustained outage challenges continuity.','life_safety':4,'mission':5,'operations':5,'financial':4,'legal_regulatory':3,'reputation':4,'recovery':5})
    capability=post(client,'/api/capabilities',h,{'assessment_id':aid,'scenario_id':scenario['id'],'name':'Continuity','required_outcome':'Restore service.','measurement_type':'Percentage','measurement_unit':'%','comparator':'>=','required_standard':95,'current_performance':55})
    future=(date.today()+timedelta(days=120)).isoformat()
    evidence=post(client,'/api/evidence',h,{'assessment_id':aid,'capability_id':capability['id'],'scenario_id':scenario['id'],'title':'Continuity exercise','verification_status':'Verified','valid_until':future})
    other_evidence=post(client,'/api/evidence',h,{'assessment_id':other_aid,'title':'Boundary evidence','verification_status':'Verified','valid_until':future})
    baseline=client.get(f'/api/risk/{aid}',headers=h).json()[0]

    base_override={'assessment_id':aid,'threat_id':threat['id'],'assigned_score':72,'reason':'Professional judgment accounts for an unmodeled dependency.','authority':'Chief Risk Authority','evidence_id':evidence['id'],'review_date':future}
    for key,value in {'calculated_score':0,'assigned_band':'Low','status':'Active','created_by':'forged','review_lifecycle_status':'Current'}.items():
        response=client.post('/api/risk-overrides',headers=h,json={**base_override,key:value})
        assert response.status_code==422,(key,response.text)
    assert client.post('/api/risk-overrides',headers=h,json={**base_override,'assigned_score':101}).status_code==422
    assert client.post('/api/risk-overrides',headers=h,json={**base_override,'evidence_id':other_evidence['id']}).status_code==422
    assert client.post('/api/risk-overrides',headers=h,json={**base_override,'threat_id':other_threat['id']}).status_code==422

    override=post(client,'/api/risk-overrides',h,base_override)
    oid=override['id']
    assert override['calculated_score']==baseline['current_score'] and override['assigned_score']==72
    assert override['calculated_band']==baseline['current_band'] and override['assigned_band']==app.risk_band(72)
    assert client.put(f'/api/risk_overrides/{oid}',headers=h,json={'assigned_score':1}).status_code==404
    risk=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert risk['current_score']==baseline['current_score'] and risk['assigned_risk_score']==72
    assert risk['professional_override_applicable'] is True

    yesterday=(date.today()-timedelta(days=1)).isoformat()
    conn=app.db(); conn.execute('UPDATE evidence SET valid_until=?,lifecycle_status=? WHERE id=?',(yesterday,'Current',evidence['id'])); conn.commit(); conn.close()
    stale_risk=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert stale_risk['current_score']==baseline['current_score']
    assert stale_risk['professional_override'] is None and stale_risk['professional_override_record']['id']==oid
    assert stale_risk['professional_override_applicable'] is False and stale_risk['assigned_risk_score'] is None
    assert 'calculated risk remains authoritative' in stale_risk['professional_override_unavailable_reason']
    assert post(client,f'/api/risk-overrides/{oid}/review',h,{'next_review_date':future,'review_outcome':'Attempted renewal with stale evidence.'},409)
    client.get(f'/api/risk/{aid}',headers=h); client.get(f'/api/risk/{aid}',headers=h)
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    stale_triggers=[x for x in triggers if x['source']=='Evidence Lifecycle' and x['affected_record_id']==evidence['id'] and x['status']!='Resolved']
    assert len(stale_triggers)==1

    renewed=(date.today()+timedelta(days=365)).isoformat()
    reviewed=post(client,f'/api/evidence/{evidence["id"]}/lifecycle-review',h,{'valid_until':renewed,'review_note':'Exercise evidence remains representative after accountable review.'})
    assert reviewed['lifecycle_status']=='Current' and reviewed['verification_status']=='Verified' and reviewed['valid_until']==renewed
    restored=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert restored['assigned_risk_score']==72 and restored['professional_override_applicable'] is True
    review_date=(date.today()+timedelta(days=180)).isoformat()
    reviewed_override=post(client,f'/api/risk-overrides/{oid}/review',h,{'next_review_date':review_date,'review_outcome':'Professional basis and current Verified evidence remain valid.'})
    assert reviewed_override['review_date']==review_date and reviewed_override['last_review_by']=='V115 Authority'

    replacement=post(client,'/api/risk-overrides',h,{'assessment_id':aid,'threat_id':threat['id'],'assigned_score':64,'reason':'Updated professional judgment after dependency review.','authority':'Chief Risk Authority','review_date':review_date})
    assert replacement['supersedes_id']==oid and replacement['status']=='Active'
    conn=app.db(); prior=dict(conn.execute('SELECT * FROM risk_overrides WHERE id=?',(oid,)).fetchone()); conn.close()
    assert prior['status']=='Superseded'
    replaced_risk=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert replaced_risk['assigned_risk_score']==64 and replaced_risk['current_score']==baseline['current_score']

    replacement_id=replacement['id']
    conn=app.db(); conn.execute("UPDATE risk_overrides SET review_date=?,review_lifecycle_status='Current' WHERE id=?",(yesterday,replacement_id)); conn.commit(); conn.close()
    overdue=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert overdue['professional_override'] is None and overdue['assigned_risk_score'] is None
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    overdue_triggers=[x for x in triggers if x['source']=='Risk Override Lifecycle' and x['affected_record_id']==replacement_id and x['status']!='Resolved']
    assert len(overdue_triggers)==1
    post(client,f'/api/risk-overrides/{replacement_id}/review',h,{'next_review_date':review_date,'review_outcome':'Professional judgment was reviewed and renewed.'})
    assert client.get(f'/api/risk/{aid}',headers=h).json()[0]['assigned_risk_score']==64
    withdrawn=post(client,f'/api/risk-overrides/{replacement_id}/withdraw',h,{'reason':'The accountable authority returned to calculated risk.'})
    assert withdrawn['status']=='Withdrawn'
    final_risk=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert final_risk['professional_override'] is None and final_risk['professional_override_record'] is None
    assert final_risk['current_score']==baseline['current_score'] and final_risk['assigned_risk_score'] is None

    conn=app.db()
    audits=[dict(x) for x in conn.execute("SELECT * FROM audit_log WHERE entity_type='risk_override' AND entity_id IN (?,?) ORDER BY id",(oid,replacement_id))]
    versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='risk_overrides' AND entity_id IN (?,?) ORDER BY id",(oid,replacement_id))]
    package=collect_tenant_records(conn,1); conn.close()
    assert {'CREATE','SUPERSEDE','RISK_OVERRIDE_REVIEW','RISK_OVERRIDE_REVIEW_OVERDUE','WITHDRAW'}.issubset({x['action'] for x in audits})
    assert len(versions)>=7
    assert len([x for x in package['risk_overrides'] if x['assessment_id']==aid])==2
    assert client.get('/health/ready').json()['version']=='1.15.0'
    print('V1_15_OPERATIONAL_RISK_PROFESSIONAL_JUDGMENT_PASS',app.DB_BACKEND)


if __name__=='__main__': main()
