#!/usr/bin/env python3
"""v1.4 evidence-lifecycle governance smoke, shared by SQLite/PostgreSQL CI."""
import sys
from datetime import date, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app

def expect(r,code=200):
    assert r.status_code==code, f'{r.status_code}: {r.text}'
    return r.json() if 'application/json' in r.headers.get('content-type','') else r.text

def main():
    conn=app.db()
    assert conn.execute('SELECT COUNT(*) c FROM assessments').fetchone()['c']==1
    for version in ('0.8.0','0.9.0','1.0.0','1.1.0','1.2.0','1.3.0','1.4.0'):
        assert conn.execute('SELECT COUNT(*) c FROM schema_migrations WHERE version=?',(version,)).fetchone()['c']==1
    aid=conn.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']
    iid=conn.execute('SELECT id FROM improvements WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    tid=conn.execute('SELECT id FROM threats WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()['id']
    conn.close()
    yesterday=(date.today()-timedelta(days=1)).isoformat(); future=(date.today()+timedelta(days=30)).isoformat(); future2=(date.today()+timedelta(days=60)).isoformat()
    client=TestClient(app.app); h={'X-Salus-Role':'Assessment Director','X-Salus-User':'CI v1.4','X-Salus-Tenant':'1'}

    stale=expect(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Expired Exercise Evidence','evidence_type':'Exercise Result','verification_status':'Verified','valid_until':yesterday,'owner':'CI Owner'}))
    assert stale['verification_status']=='Verified' and stale['lifecycle_status']=='Stale'
    trigs=expect(client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h))
    active=[t for t in trigs if t['source']=='Evidence Lifecycle' and t['affected_record_id']==stale['id'] and t['status']!='Resolved']
    assert len(active)==1 and active[0]['severity']=='Moderate'
    expect(client.get('/api/dashboard',headers=h)); expect(client.get('/api/dashboard',headers=h))
    trigs=expect(client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h))
    assert len([t for t in trigs if t['source']=='Evidence Lifecycle' and t['affected_record_id']==stale['id'] and t['status']!='Resolved'])==1

    expect(client.put(f"/api/evidence/{stale['id']}",headers=h,json={'lifecycle_status':'Current'}),409)
    expect(client.put(f"/api/evidence/{stale['id']}",headers=h,json={'valid_until':future}),409)
    reviewed=expect(client.post(f"/api/evidence/{stale['id']}/lifecycle-review",headers=h,json={'valid_until':future,'outcome':'Source revalidated against current exercise record.'}))
    assert reviewed['lifecycle_status']=='Current' and reviewed['valid_until']==future and reviewed['lifecycle_reviewed_by']=='CI v1.4'

    ev=expect(client.post('/api/evidence',headers=h,json={'assessment_id':aid,'title':'Current Validation Evidence','evidence_type':'Performance Data','verification_status':'Verified','valid_until':future2,'owner':'Program Owner'}))
    expect(client.post('/api/decisions',headers=h,json={'assessment_id':aid,'improvement_id':iid,'decision_type':'Approve','authority':'CI Executive','rationale':'Authorize improvement for lifecycle test.'}))
    expect(client.put(f'/api/improvements/{iid}',headers=h,json={'status':'Complete'}))
    validated=expect(client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':ev['id'],'validation_status':'Validated','validation_outcome':'Observed performance meets validation criteria.','validated_effectiveness_percent':100}))
    assert validated['validation_status']=='Validated'
    before=next(r for r in expect(client.get(f'/api/risk/{aid}',headers=h)) if r['threat_id']==tid)
    assert before['validated_improvements']>=1

    override=expect(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':70,'reason':'Professional judgment supported by current evidence.','authority':'CI Executive','evidence_id':ev['id'],'review_date':future2}))
    assert override['status']=='Active'
    expired=expect(client.put(f"/api/evidence/{ev['id']}",headers=h,json={'valid_until':yesterday}))
    assert expired['lifecycle_status']=='Stale'
    after=next(r for r in expect(client.get(f'/api/risk/{aid}',headers=h)) if r['threat_id']==tid)
    assert after['validated_improvements']==0 and after['validated_residual_score']==after['current_score']
    assert after['professional_override']['id']==override['id'] and after['professional_override_evidence_current'] is False
    expect(client.post('/api/risk-overrides',headers=h,json={'assessment_id':aid,'threat_id':tid,'assigned_score':65,'reason':'Stale evidence must not support a new override.','authority':'CI Executive','evidence_id':ev['id']}),409)
    trigs=expect(client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h))
    active=[t for t in trigs if t['source']=='Evidence Lifecycle' and t['affected_record_id']==ev['id'] and t['status']!='Resolved']
    assert len(active)==1 and active[0]['severity']=='High'

    renewed=expect(client.post(f"/api/evidence/{ev['id']}/lifecycle-review",headers=h,json={'valid_until':future2,'outcome':'Evidence independently revalidated.'}))
    assert renewed['lifecycle_status']=='Current'
    conn=app.db(); conn.execute("UPDATE evidence SET valid_until=?,lifecycle_status='Current',stale_reason='',stale_at='' WHERE id=?",(yesterday,ev['id'])); conn.commit(); conn.close()
    dash=expect(client.get('/api/dashboard',headers=h)); assert dash['stats']['stale_evidence']>=1
    export=expect(client.get(f'/api/export/{aid}',headers=h)); assert export['evidence_lifecycle']['stale']>=1
    csv_text=expect(client.get(f'/api/report/{aid}/executive.csv',headers=h)); assert 'Evidence Lifecycle' in csv_text and 'Stale Evidence' in csv_text
    trigs=expect(client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h))
    assert len([t for t in trigs if t['source']=='Evidence Lifecycle' and t['affected_record_id']==ev['id'] and t['status']!='Resolved'])==1

    conn=app.db(); records=app.collect_tenant_records(conn,1); conn.close()
    bev=next(x for x in records['evidence'] if x['id']==ev['id'])
    assert bev['lifecycle_status']=='Stale' and bev['valid_until']==yesterday and not app.validate_records(records,1)
    assert expect(client.get('/health/ready'))['version']=='1.4.0'
    assert expect(client.get('/api/system/mode',headers=h))['version']=='1.4.0'
    assert all(r['risk_methodology_version']=='1.1.0' for r in expect(client.get(f'/api/risk/{aid}',headers=h)))
    js=(ROOT/'static'/'app.js').read_text(encoding='utf-8')
    assert 'Lifecycle Review' in js and "lifecycle_status==='Current'" in js
    print('V1_4_EVIDENCE_LIFECYCLE_PASS',app.DB_BACKEND)

if __name__=='__main__': main()
