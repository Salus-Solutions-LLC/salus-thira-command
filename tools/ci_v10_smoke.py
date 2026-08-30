#!/usr/bin/env python3
"""Release-gate smoke tests shared by SQLite and PostgreSQL CI."""
from starlette.testclient import TestClient
import app


def main():
    # Core schema and direction-aware measurement semantics.
    c=app.db()
    assert c.execute('SELECT COUNT(*) c FROM assessments').fetchone()['c']==1
    for version in ('0.8.0','0.9.0','1.0.0'):
        assert c.execute('SELECT COUNT(*) c FROM schema_migrations WHERE version=?',(version,)).fetchone()['c']==1
    cols={r['name'] for r in c.execute('PRAGMA table_info(capabilities)')}
    assert {'measurement_type','measurement_unit','comparator'} <= cols
    aid=c.execute('SELECT id FROM assessments ORDER BY id LIMIT 1').fetchone()['id']
    imp=c.execute('SELECT id FROM improvements WHERE assessment_id=? ORDER BY id LIMIT 1',(aid,)).fetchone()
    impid=imp['id'] if imp else None
    c.close()

    assert app.capability_effectiveness(10,8,'<=','Time')==100.0
    assert app.capability_effectiveness(10,12,'<=','Time')==83.3
    assert app.capability_gap(10,12,'<=')==2.0
    assert app.capability_effectiveness(95,72,'>=','Percentage')==75.8
    assert app.capability_effectiveness(1,1,'=','Binary')==100.0
    assert app.capability_effectiveness(1,0,'=','Binary')==0.0

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'CI','X-Salus-Tenant':'1'}
    payload={
        'assessment_id':aid,
        'name':'CI Response Time',
        'required_outcome':'Perform within the required time.',
        'operating_conditions':'Release-gate exercise conditions.',
        'performance_metric':'Minutes from authorization to initiation',
        'measurement_type':'Time','measurement_unit':'minutes','comparator':'<=',
        'required_standard':10,'current_performance':8,'confidence':'High'
    }
    r=client.post('/api/capabilities',headers=h,json=payload); assert r.status_code==200,r.text
    cid=r.json()['id']
    row=next(x for x in client.get(f'/api/capabilities?assessment_id={aid}',headers=h).json() if x['id']==cid)
    assert row['attainment_percent']==100.0 and row['performance_gap']==0 and row['target_status']=='Met'
    r=client.put(f'/api/capabilities/{cid}',headers=h,json={'current_performance':12}); assert r.status_code==200,r.text
    row=next(x for x in client.get(f'/api/capabilities?assessment_id={aid}',headers=h).json() if x['id']==cid)
    assert row['attainment_percent']==83.3 and row['performance_gap']==2.0 and row['target_status']=='Near Target'

    binary=payload|{
        'name':'CI Binary Control','measurement_type':'Binary','measurement_unit':'yes/no',
        'comparator':'=','required_standard':1,'current_performance':1
    }
    r=client.post('/api/capabilities',headers=h,json=binary); assert r.status_code==200,r.text
    bad=binary|{'name':'CI Invalid Binary','comparator':'>='}
    assert client.post('/api/capabilities',headers=h,json=bad).status_code==422

    # Accepted risk remains an accountable lifecycle record.
    decision={
        'assessment_id':aid,'improvement_id':impid,'decision_type':'Accept Risk',
        'authority':'CI Executive','rationale':'Residual risk accepted for validation.',
        'conditions':'Reconsider on material change.','implementation_owner':'CI Owner',
        'expected_residual_risk':'Moderate residual exposure remains.','review_date':'2099-12-31'
    }
    r=client.post('/api/decisions',headers=h,json=decision); assert r.status_code==200,r.text
    risks=client.get(f'/api/accepted_risks?assessment_id={aid}',headers=h).json()
    risk=next(x for x in risks if x['decision_id']==r.json()['id'])
    assert risk['status']=='Active'
    assert client.put(f"/api/accepted_risks/{risk['id']}",headers=h,json={'status':'Closed'}).status_code==422
    r=client.put(f"/api/accepted_risks/{risk['id']}",headers=h,json={'status':'Closed','closure_basis':'CI validated closure basis.'})
    assert r.status_code==200,r.text

    dash=client.get('/api/dashboard',headers=h); assert dash.status_code==200,dash.text
    assert 0 <= dash.json()['stats']['avg_capability_attainment'] <= 100
    exported=client.get(f'/api/export/{aid}',headers=h); assert exported.status_code==200,exported.text
    assert any(x['id']==cid and x['attainment_percent']==83.3 for x in exported.json()['capability_performance'])
    assert 'Capability Performance' in client.get(f'/api/report/{aid}/executive.csv',headers=h).text
    assert 'Capability Performance' in client.get(f'/api/report/{aid}/executive.html',headers=h).text
    assert client.get('/health/ready').json()['version']=='1.0.0'
    print('V1_0_RUNTIME_SMOKE_PASS', app.DB_BACKEND)

if __name__=='__main__': main()
