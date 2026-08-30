#!/usr/bin/env python3
"""v1.3 professional-risk-override release smoke, shared by SQLite/PostgreSQL CI."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app


def assert_status(response, expected):
    assert response.status_code==expected, f'{response.status_code}: {response.text}'
    return response


def main():
    conn=app.db()
    assert conn.execute('SELECT COUNT(*) c FROM assessments').fetchone()['c']==1
    for version in ('0.8.0','0.9.0','1.0.0','1.1.0','1.2.0','1.3.0'):
        assert conn.execute('SELECT COUNT(*) c FROM schema_migrations WHERE version=?',(version,)).fetchone()['c']==1
    aid=conn.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']
    iid=conn.execute('SELECT id FROM improvements WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    tid=conn.execute('SELECT id FROM threats WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    conn.close()

    # Retain v1.0 direction-aware measurement semantics.
    assert app.capability_effectiveness(10,8,'<=','Time')==100.0
    assert app.capability_effectiveness(10,12,'<=','Time')==83.3
    assert app.capability_effectiveness(95,72,'>=','Percentage')==75.8
    assert app.capability_effectiveness(1,1,'=','Binary')==100.0

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'CI v1.3','X-Salus-Tenant':'1'}

    # Retain governed residual-risk behavior from v1.1.
    baseline=next(r for r in client.get(f'/api/risk/{aid}',headers=h).json() if r['threat_id']==tid)
    base_state=(baseline['current_score'],baseline['predicted_residual_score'],baseline['validated_residual_score'])
    assert baseline['professional_override'] is None
    assert baseline['assigned_risk_score'] is None

    # v1.3 professional judgment requires decision authority.
    low={'X-Salus-Role':'Lead Assessor','X-Salus-User':'CI Lead','X-Salus-Tenant':'1'}
    denied=client.post('/api/risk-overrides',headers=low,json={'assessment_id':aid,'threat_id':tid,'assigned_score':80,'reason':'Lead assessor cannot make executive risk assignment.','authority':'CI Lead'})
    assert_status(denied,403)

    # Supporting evidence, when cited, must be same-assessment and Verified.
    pending=assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Pending Override Evidence','evidence_type':'SME Judgment','verification_status':'Pending'}),200).json()
    bad=client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':82,'reason':'Pending evidence must not support an override.','authority':'CI Executive','evidence_id':pending['id']})
    assert_status(bad,409)
    verified=assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Verified Override Evidence','evidence_type':'SME Judgment','verification_status':'Verified'}),200).json()

    # Create first professional override. It preserves calculated risk and stores assigned risk separately.
    first=assert_status(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':85,'reason':'Verified professional judgment identifies concentration risk not represented in the quantitative inputs.','authority':'CI Executive','evidence_id':verified['id'],'review_date':'2027-01-15'}),200).json()
    assert first['status']=='Active'
    assert first['assigned_band']=='Critical'
    assert float(first['calculated_score'])==float(baseline['current_score'])
    assert first['calculated_band']==baseline['current_band']
    r1=next(r for r in client.get(f'/api/risk/{aid}',headers=h).json() if r['threat_id']==tid)
    assert (r1['current_score'],r1['predicted_residual_score'],r1['validated_residual_score'])==base_state
    assert r1['professional_override']['id']==first['id']
    assert r1['assigned_risk_score']==85
    assert r1['assigned_risk_band']=='Critical'

    # A new override supersedes, rather than overwrites, the prior professional record.
    second=assert_status(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':45,'reason':'New verified operating evidence supports a lower professional assignment while calculated risk remains unchanged.','authority':'CI Executive','evidence_id':verified['id'],'review_date':'2027-03-15'}),200).json()
    assert second['status']=='Active' and second['supersedes_id']==first['id']
    history=client.get(f'/api/risk_overrides?assessment_id={aid}',headers=h).json()
    by_id={r['id']:r for r in history}
    assert by_id[first['id']]['status']=='Superseded'
    assert by_id[second['id']]['status']=='Active'
    r2=next(r for r in client.get(f'/api/risk/{aid}',headers=h).json() if r['threat_id']==tid)
    assert (r2['current_score'],r2['predicted_residual_score'],r2['validated_residual_score'])==base_state
    assert r2['assigned_risk_score']==45 and r2['assigned_risk_band']=='Moderate'

    # Direct mutation is not permitted; withdrawal is a governed action with a reason.
    assert_status(client.put(f'/api/risk_overrides/{second["id"]}',headers=h,json={'assigned_score':10}),404)
    withdrawn=assert_status(client.post(f'/api/risk-overrides/{second["id"]}/withdraw',headers=h,json={'reason':'Override withdrawn after executive review; calculated model remains controlling.'}),200).json()
    assert withdrawn['status']=='Withdrawn' and withdrawn['withdrawn_reason']
    r3=next(r for r in client.get(f'/api/risk/{aid}',headers=h).json() if r['threat_id']==tid)
    assert (r3['current_score'],r3['predicted_residual_score'],r3['validated_residual_score'])==base_state
    assert r3['professional_override'] is None and r3['assigned_risk_score'] is None
    assert_status(client.post(f'/api/risk-overrides/{second["id"]}/withdraw',headers=h,json={'reason':'Cannot withdraw twice'}),409)

    # Cross-assessment threat/evidence relationships fail closed.
    a2=assert_status(client.post('/api/assessments',headers=h,json={'name':'Override Boundary Assessment','organization':'Salus CI'}),200).json()['id']
    t2=assert_status(client.post('/api/threats',headers=h,json={'assessment_id':a2,'name':'Other Assessment Threat','category':'Cyber'}),200).json()
    e2=assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':a2,'title':'Other Assessment Evidence','evidence_type':'SME Judgment','verification_status':'Verified'}),200).json()
    assert_status(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':t2['id'],'assigned_score':70,'reason':'Cross threat must fail.','authority':'CI Executive'}),422)
    assert_status(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':70,'reason':'Cross evidence must fail.','authority':'CI Executive','evidence_id':e2['id']}),422)

    # Traceability, export, and reports retain the complete professional judgment history.
    trace=client.get(f'/api/trace/{aid}',headers=h).json()
    tr=next(t for t in trace['threats'] if t['id']==tid)
    assert len(tr['risk_overrides'])>=2 and tr['active_risk_override'] is None
    pkg=client.get(f'/api/export/{aid}',headers=h).json()
    assert len(pkg['risk_overrides'])>=2
    assert pkg['risk_methodology_version']=='1.1.0'
    csv_text=client.get(f'/api/report/{aid}/executive.csv',headers=h).text
    html_text=client.get(f'/api/report/{aid}/executive.html',headers=h).text
    assert 'Professional Risk Override Register' in csv_text
    assert 'Professional Risk Override Register' in html_text

    # Portable backup includes governed override history.
    conn=app.db(); records=app.collect_tenant_records(conn,1); conn.close()
    assert 'risk_overrides' in records and len(records['risk_overrides'])>=2
    assert not app.validate_records(records,1)

    # Application version advances while scoring methodology remains unchanged.
    assert client.get('/health/ready').json()['version']=='1.3.0'
    assert client.get('/api/system/mode',headers=h).json()['version']=='1.3.0'
    assert all(r['risk_methodology_version']=='1.1.0' for r in client.get(f'/api/risk/{aid}',headers=h).json())

    # UI states the separation explicitly and exposes governed actions, not editable calculated values.
    js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    assert 'Calculated risk and professional judgment are separate records.' in js
    assert '/api/risk-overrides' in js and 'withdrawRiskOverride' in js
    print('V1_3_PROFESSIONAL_RISK_OVERRIDE_PASS',app.DB_BACKEND)


if __name__=='__main__':
    main()
