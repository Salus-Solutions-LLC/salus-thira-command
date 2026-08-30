#!/usr/bin/env python3
"""v1.2 relational-integrity release smoke, shared by SQLite/PostgreSQL CI."""
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
    for version in ('0.8.0','0.9.0','1.0.0','1.1.0','1.2.0'):
        assert conn.execute('SELECT COUNT(*) c FROM schema_migrations WHERE version=?',(version,)).fetchone()['c']==1
    aid=conn.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']
    iid=conn.execute('SELECT id FROM improvements WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    conn.close()

    # Retain v1.0 direction-aware measurement semantics.
    assert app.capability_effectiveness(10,8,'<=','Time')==100.0
    assert app.capability_effectiveness(10,12,'<=','Time')==83.3
    assert app.capability_effectiveness(95,72,'>=','Percentage')==75.8
    assert app.capability_effectiveness(1,1,'=','Binary')==100.0

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'CI v1.2','X-Salus-Tenant':'1'}

    # Retain v1.1 governed residual-risk behavior.
    baseline=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert baseline['predicted_residual_score']==baseline['current_score']==baseline['validated_residual_score']
    assert_status(client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':iid,'decision_type':'Approve','authority':'CI Executive','rationale':'Release validation approval.'}),200)
    approved=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert approved['current_score']==baseline['current_score']
    assert approved['predicted_residual_score'] < approved['current_score']
    assert approved['validated_residual_score']==approved['current_score']
    assert_status(client.put(f'/api/improvements/{iid}',headers=h,json={'status':'Complete'}),200)
    completed=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert completed['validated_residual_score']==completed['current_score']
    pending=assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Pending Validation Evidence','evidence_type':'Exercise Result','verification_status':'Pending'}),200).json()
    assert_status(client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':pending['id'],'validation_status':'Validated','validation_outcome':'Not verified','validated_effectiveness_percent':100}),409)
    verified=assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Verified Validation Exercise','evidence_type':'Exercise Result','verification_status':'Verified'}),200).json()
    assert_status(client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':verified['id'],'validation_status':'Partially Validated','validation_outcome':'Half of expected benefit demonstrated.','validated_effectiveness_percent':50}),200)
    partial=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert partial['predicted_residual_score'] < partial['validated_residual_score'] < partial['current_score']
    assert partial['risk_methodology_version']=='1.1.0'
    assert_status(client.put(f'/api/evidence/{verified["id"]}',headers=h,json={'verification_status':'Pending'}),200)
    revoked=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert revoked['validated_residual_score']==revoked['current_score']
    assert_status(client.put(f'/api/evidence/{verified["id"]}',headers=h,json={'verification_status':'Verified'}),200)
    assert_status(client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':verified['id'],'validation_status':'Failed','validation_outcome':'Expected benefit was not demonstrated.','validated_effectiveness_percent':0}),200)
    assert_status(client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':iid,'decision_type':'Defer','authority':'CI Executive','rationale':'Deferred after failed validation.'}),200)
    deferred=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert deferred['predicted_residual_score']==deferred['current_score']==deferred['validated_residual_score']

    # v1.2: assessment-scoped relational integrity.
    a2=assert_status(client.post('/api/assessments',headers=h,json={'name':'Relational Integrity Assessment','organization':'Salus CI'}),200).json()['id']
    t1=client.get(f'/api/threats?assessment_id={aid}',headers=h).json()[0]
    t2=assert_status(client.post('/api/threats',headers=h,json={'assessment_id':a2,'name':'Assessment Two Threat','category':'Cyber'}),200).json()

    # A relationship may never cross assessment boundaries.
    cross=client.post('/api/scenarios',headers=h,json={'assessment_id':aid,'threat_id':t2['id'],'title':'Cross-assessment scenario','narrative':'must fail'})
    assert_status(cross,422); assert 'different assessment' in cross.text

    # Build a valid same-assessment chain in assessment two.
    s2=assert_status(client.post('/api/scenarios',headers=h,json={'assessment_id':a2,'threat_id':t2['id'],'title':'Assessment Two Scenario','narrative':'valid chain'}),200).json()
    c2=assert_status(client.post('/api/capabilities',headers=h,json={'assessment_id':a2,'scenario_id':s2['id'],'name':'Assessment Two Capability','required_outcome':'Perform required task','measurement_type':'Time','measurement_unit':'minutes','comparator':'<=','required_standard':10,'current_performance':8}),200).json()
    g2=assert_status(client.post('/api/gaps',headers=h,json={'assessment_id':a2,'capability_id':c2['id'],'description':'Assessment two gap','severity':'High'}),200).json()
    i2=assert_status(client.post('/api/improvements',headers=h,json={'assessment_id':a2,'gap_id':g2['id'],'title':'Assessment two improvement'}),200).json()
    assert_status(client.post('/api/decisions',headers=h,json={'assessment_id':a2,'improvement_id':i2['id'],'decision_type':'Approve','authority':'CI Executive','rationale':'Valid same-assessment chain.'}),200)

    # Cross-assessment create attempts are rejected for every principal relationship.
    assert_status(client.post('/api/gaps',headers=h,json={'assessment_id':aid,'capability_id':c2['id'],'description':'Cross gap'}),422)
    assert_status(client.post('/api/improvements',headers=h,json={'assessment_id':aid,'gap_id':g2['id'],'title':'Cross improvement'}),422)
    assert_status(client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':i2['id'],'decision_type':'Approve','authority':'CI Executive','rationale':'Cross decision'}),422)
    assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'capability_id':c2['id'],'title':'Cross evidence','evidence_type':'Observation'}),422)
    assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'scenario_id':s2['id'],'title':'Cross scenario evidence','evidence_type':'Observation'}),422)
    assert_status(client.post('/api/reassessment_triggers',headers=h,json={'assessment_id':aid,'source':'Manual','trigger_type':'CI Cross Link','description':'Must fail','affected_record_type':'improvement','affected_record_id':i2['id']}),422)

    # Valid optional standalone evidence remains supported.
    assert_status(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'capability_id':None,'scenario_id':None,'title':'Standalone Evidence','evidence_type':'Observation'}),200)

    # Existing governed child records cannot be moved to another assessment.
    move=client.put(f'/api/threats/{t2["id"]}',headers=h,json={'assessment_id':aid})
    assert_status(move,409); assert 'immutable' in move.text.lower()

    # Relationship updates are revalidated, not just creates.
    cross_update=client.put(f'/api/scenarios/{s2["id"]}',headers=h,json={'threat_id':t1['id']})
    assert_status(cross_update,422)
    cross_update=client.put(f'/api/gaps/{g2["id"]}',headers=h,json={'capability_id':client.get(f"/api/capabilities?assessment_id={aid}",headers=h).json()[0]['id']})
    assert_status(cross_update,422)

    # Assessment-scoped list endpoints do not leak records from another assessment.
    assert all(int(r['assessment_id'])==aid for r in client.get(f'/api/threats?assessment_id={aid}',headers=h).json())
    assert all(int(r['assessment_id'])==a2 for r in client.get(f'/api/threats?assessment_id={a2}',headers=h).json())

    # UI no longer asks users to type principal relationship IDs or child assessment IDs.
    js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    for stale in ("'Threat ID','number'","'Scenario ID','number'","'Capability ID','number'","'Gap ID','number'","'Improvement ID','number'","'Assessment ID','number'"):
        assert stale not in js, stale
    assert "'relation'" in js and 'relationOptions' in js and 'data.assessment_id=activeAssessmentId' in js

    # Application version advances while the risk methodology stays v1.1.
    assert client.get('/health/ready').json()['version']=='1.2.0'
    assert client.get('/api/system/mode',headers=h).json()['version']=='1.2.0'
    pkg=client.get(f'/api/export/{aid}',headers=h).json()
    assert pkg['risk_methodology_version']=='1.1.0'
    print('V1_2_RELATIONAL_INTEGRITY_PASS',app.DB_BACKEND)


if __name__=='__main__':
    main()
