#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND']='sqlite'
os.environ['SALUS_DB_PATH']=str(Path(TMP.name)/'v113-smoke.db')
os.environ['SALUS_AUTH_MODE']='prototype'
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def main():
    spec=importlib.util.spec_from_file_location('ci_v112',ROOT/'tools'/'ci_v112_smoke.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    actual=app.APP_VERSION
    try: app.APP_VERSION='1.12.0';previous.main()
    finally: app.APP_VERSION=actual

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V113 CI','X-Salus-Tenant':'1','X-Salus-Clearance':'Highly Sensitive'}
    aid=client.post('/api/assessments',headers=h,json={'name':'V113 Evidence Lifecycle Assessment','organization':'Member Client Alpha'}).json()['id']
    threat=client.post('/api/threats',headers=h,json={'assessment_id':aid,'name':'Evidence-dependent threat','category':'Operational'}).json()
    scenario=client.post('/api/scenarios',headers=h,json={'assessment_id':aid,'threat_id':threat['id'],'title':'Evidence lifecycle scenario','narrative':'A controlled scenario requiring current verified evidence.'}).json()
    capability=client.post('/api/capabilities',headers=h,json={'assessment_id':aid,'scenario_id':scenario['id'],'name':'Continuity capability','measurement_type':'Percentage','measurement_unit':'%','comparator':'>=','required_standard':100,'current_performance':80}).json()
    yesterday=(date.today()-timedelta(days=1)).isoformat();future=(date.today()+timedelta(days=365)).isoformat()
    payload={'assessment_id':aid,'capability_id':capability['id'],'scenario_id':scenario['id'],'title':'Continuity exercise record','evidence_type':'Exercise','source':'Controlled exercise','owner':'Evidence Owner','evidence_date':yesterday,'reliability':'High','verification_status':'Verified','sensitivity':'Standard','valid_until':yesterday,'notes':'Exercise timing and evaluator record.'}
    response=client.post('/api/evidence',headers=h,json=payload)
    assert response.status_code==200,response.text
    evidence=response.json();eid=evidence['id']
    assert evidence['verification_status']=='Verified'
    assert evidence['lifecycle_status']=='Stale'
    assert evidence['stale_reason'].startswith('Validity date expired on ')
    assert evidence['stale_at']

    first=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    stale=[x for x in first if x['source']=='Evidence Lifecycle' and x['affected_record_id']==eid and x['status']=='Open']
    assert len(stale)==1,stale
    for _ in range(3): client.get(f'/api/evidence?assessment_id={aid}',headers=h)
    repeated=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    assert len([x for x in repeated if x['source']=='Evidence Lifecycle' and x['affected_record_id']==eid and x['status']=='Open'])==1

    for forged in ({'lifecycle_status':'Current'},{'stale_reason':''},{'stale_at':''},{'last_lifecycle_review_by':'forged'}):
        blocked=client.put(f'/api/evidence/{eid}',headers=h,json=forged)
        assert blocked.status_code==409,(forged,blocked.text)
    for key,value in {'tenant_id':2,'created_at':'2000-01-01T00:00:00Z','lifecycle_status':'Current','stale_reason':'','last_lifecycle_review_by':'forged'}.items():
        forged=client.post('/api/evidence',headers=h,json={**payload,key:value})
        assert forged.status_code==422,(key,forged.text)
    assert client.post('/api/evidence',headers=h,json={**payload,'title':'   '}).status_code==422
    assert client.post('/api/evidence',headers=h,json={**payload,'evidence_date':'not-a-date'}).status_code==422

    reviewed=client.post(f'/api/evidence/{eid}/lifecycle-review',headers=h,json={'valid_until':future,'review_note':'Source and integrity were reviewed; continued use is authorized.'})
    assert reviewed.status_code==200,reviewed.text
    current=reviewed.json()
    assert current['verification_status']=='Verified'
    assert current['lifecycle_status']=='Current' and current['valid_until']==future
    assert not current['stale_reason'] and not current['stale_at']
    assert current['last_lifecycle_review_by']=='V113 CI' and current['last_lifecycle_review_at']
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    resolved=[x for x in triggers if x['source']=='Evidence Lifecycle' and x['affected_record_id']==eid]
    assert len(resolved)==1 and resolved[0]['status']=='Resolved' and 'restored to Current' in resolved[0]['resolution']

    conn=app.db()
    audits=[dict(x) for x in conn.execute("SELECT * FROM audit_log WHERE entity_id=? AND action IN ('EVIDENCE_STALE','EVIDENCE_LIFECYCLE_REVIEW') ORDER BY id",(eid,))]
    versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='evidence' AND entity_id=? ORDER BY version_no",(eid,))]
    package=collect_tenant_records(conn,1);conn.close()
    assert {x['action'] for x in audits}=={'EVIDENCE_STALE','EVIDENCE_LIFECYCLE_REVIEW'}
    assert len(versions)>=3
    assert any(x['id']==eid and x['lifecycle_status']=='Current' for x in package['evidence'])
    assert client.get('/health/ready').json()['version']=='1.13.0'
    print('V1_13_OPERATIONAL_EVIDENCE_LIFECYCLE_WORKSPACE_PASS',app.DB_BACKEND)


if __name__=='__main__': main()
