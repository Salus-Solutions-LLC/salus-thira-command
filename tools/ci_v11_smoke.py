#!/usr/bin/env python3
"""v1.1 governed residual-risk release smoke, shared by SQLite/PostgreSQL CI."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app


def main():
    c=app.db()
    assert c.execute('SELECT COUNT(*) c FROM assessments').fetchone()['c']==1
    for version in ('0.8.0','0.9.0','1.0.0','1.1.0'):
        assert c.execute('SELECT COUNT(*) c FROM schema_migrations WHERE version=?',(version,)).fetchone()['c']==1
    icols={r['name'] for r in c.execute('PRAGMA table_info(improvements)')}
    assert {'validation_status','validation_evidence_id','validation_outcome','validated_effectiveness_percent','validated_by','validated_at'} <= icols
    wcols={r['name'] for r in c.execute('PRAGMA table_info(assessment_weights)')}
    assert 'risk_methodology_version' in wcols
    aid=c.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']
    iid=c.execute('SELECT id FROM improvements WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    c.close()

    # Retain v1.0 direction-aware capability semantics.
    assert app.capability_effectiveness(10,8,'<=','Time')==100.0
    assert app.capability_effectiveness(10,12,'<=','Time')==83.3
    assert app.capability_effectiveness(95,72,'>=','Percentage')==75.8
    assert app.capability_effectiveness(1,1,'=','Binary')==100.0

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'CI v1.1','X-Salus-Tenant':'1'}
    baseline=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert baseline['predicted_residual_score']==baseline['current_score']==baseline['validated_residual_score']

    # Approval affects forecast only.
    r=client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':iid,'decision_type':'Approve','authority':'CI Executive','rationale':'Release validation approval.'})
    assert r.status_code==200,r.text
    approved=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert approved['current_score']==baseline['current_score']
    assert approved['predicted_residual_score'] < approved['current_score']
    assert approved['validated_residual_score']==approved['current_score']

    # Completion alone still earns no validated risk credit.
    r=client.put(f'/api/improvements/{iid}',headers=h,json={'status':'Complete'}); assert r.status_code==200,r.text
    completed=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert completed['validated_residual_score']==completed['current_score']
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    assert any(t['affected_record_type']=='improvement' and t['affected_record_id']==iid and t['status']=='Open' for t in triggers)

    # Validation requires currently Verified evidence.
    pending=client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Pending Validation Evidence','evidence_type':'Exercise Result','verification_status':'Pending'}); assert pending.status_code==200,pending.text
    r=client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':pending.json()['id'],'validation_status':'Validated','validation_outcome':'Not yet verified','validated_effectiveness_percent':100})
    assert r.status_code==409,r.text
    verified=client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Verified Validation Exercise','evidence_type':'Exercise Result','verification_status':'Verified'}); assert verified.status_code==200,verified.text
    eid=verified.json()['id']
    r=client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':eid,'validation_status':'Partially Validated','validation_outcome':'Exercise demonstrated half of expected benefit.','validated_effectiveness_percent':50})
    assert r.status_code==200,r.text
    partial=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert partial['current_score']==completed['current_score']
    assert partial['predicted_residual_score'] < partial['validated_residual_score'] < partial['current_score']
    assert partial['validated_improvements']==1 and partial['risk_methodology_version']=='1.1.0'

    # Governed fields cannot be edited directly.
    assert client.put(f'/api/improvements/{iid}',headers=h,json={'validation_status':'Validated'}).status_code==409

    # Evidence downgrade dynamically revokes validated credit.
    r=client.put(f'/api/evidence/{eid}',headers=h,json={'verification_status':'Pending'}); assert r.status_code==200,r.text
    revoked=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert revoked['validated_residual_score']==revoked['current_score'] and revoked['validated_improvements']==0
    client.put(f'/api/evidence/{eid}',headers=h,json={'verification_status':'Verified'})

    # Failed validation earns zero credit and opens corrective action.
    r=client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':eid,'validation_status':'Failed','validation_outcome':'Expected benefit was not demonstrated.','validated_effectiveness_percent':0}); assert r.status_code==200,r.text
    failed=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert failed['validated_residual_score']==failed['current_score'] and failed['validated_improvements']==0
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    assert any(t['trigger_type']=='Corrective Action Required' and t['affected_record_id']==iid and t['status']=='Open' for t in triggers)

    # Latest executive decision controls forecast; historical approval cannot linger.
    r=client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':iid,'decision_type':'Defer','authority':'CI Executive','rationale':'Deferred after failed validation.'}); assert r.status_code==200,r.text
    deferred=client.get(f'/api/risk/{aid}',headers=h).json()[0]
    assert deferred['approved_improvements']==0
    assert deferred['predicted_residual_score']==deferred['current_score']==deferred['validated_residual_score']

    # Reports/exports explicitly distinguish risk states.
    csv=client.get(f'/api/report/{aid}/executive.csv',headers=h); assert csv.status_code==200 and 'Predicted Residual' in csv.text and 'Validated Residual' in csv.text
    html=client.get(f'/api/report/{aid}/executive.html',headers=h); assert html.status_code==200 and 'Predicted Residual' in html.text and 'Validated Residual' in html.text
    pkg=client.get(f'/api/export/{aid}',headers=h).json(); assert pkg['risk_methodology_version']=='1.1.0'
    assert client.get('/health/ready').json()['version']=='1.1.0'
    print('V1_1_GOVERNED_RESIDUAL_RISK_PASS', app.DB_BACKEND)

if __name__=='__main__': main()
