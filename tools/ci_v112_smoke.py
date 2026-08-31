#!/usr/bin/env python3
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND']='sqlite'
os.environ['SALUS_DB_PATH']=str(Path(TMP.name)/'v112-smoke.db')
os.environ['SALUS_AUTH_MODE']='prototype'
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def main():
    spec=importlib.util.spec_from_file_location('ci_v111',ROOT/'tools'/'ci_v111_smoke.py')
    previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)
    actual=app.APP_VERSION
    try: app.APP_VERSION='1.11.0';previous.main()
    finally: app.APP_VERSION=actual

    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V112 CI','X-Salus-Tenant':'1'}
    aid=client.post('/api/assessments',headers=h,json={'name':'V112 Capability Target Assessment','organization':'Member Client Alpha'}).json()['id']
    threat=client.post('/api/threats',headers=h,json={'assessment_id':aid,'name':'Communications disruption','category':'Technological'}).json()
    scenario=client.post('/api/scenarios',headers=h,json={'assessment_id':aid,'threat_id':threat['id'],'title':'Primary communications outage','narrative':'Primary voice and data communications become unavailable during operations.'}).json()
    payload={'assessment_id':aid,'scenario_id':scenario['id'],'name':'Emergency notification initiation','mission_area':'Protection / Response','capability_family':'Communications','required_outcome':'Initiate notifications within the approved target.','operating_conditions':'Primary communications unavailable and cellular service degraded.','performance_metric':'Minutes from authorization to initial notification','measurement_type':'Time','measurement_unit':'minutes','comparator':'<=','required_standard':10,'current_performance':12,'responsible_function':'Security Operations','owner':'Program Owner','dependencies':'Contact data and alternate delivery channel','evidence_required':'Exercise timing records','confidence':'High','last_validated':'2026-08-30','next_validation':'2027-08-30'}
    response=client.post('/api/capabilities',headers=h,json=payload)
    assert response.status_code==200,response.text
    capability=response.json();cid=capability['id']
    assert capability['assessment_id']==aid and capability['scenario_id']==scenario['id']
    assert capability['measurement_type']=='Time' and capability['comparator']=='<='
    assert capability['last_validated']=='2026-08-30' and capability['next_validation']=='2027-08-30'
    listed=client.get(f'/api/capabilities?assessment_id={aid}',headers=h).json();row=next(x for x in listed if x['id']==cid)
    assert row['attainment_percent']==83.3 and row['performance_gap']==2.0 and row['target_status']=='Near Target'

    for key,value in {'tenant_id':2,'version':99,'created_at':'2000-01-01T00:00:00Z','attainment_percent':100,'target_status':'Met'}.items():
        forged=client.post('/api/capabilities',headers=h,json={**payload,key:value});assert forged.status_code==422,(key,forged.text)
    assert client.post('/api/capabilities',headers=h,json={**payload,'name':'   '}).status_code==422
    assert client.post('/api/capabilities',headers=h,json={**payload,'last_validated':'not-a-date'}).status_code==422
    assert client.post('/api/capabilities',headers=h,json={**payload,'measurement_type':'Binary','comparator':'>=','required_standard':1,'current_performance':1}).status_code==422
    binary=client.post('/api/capabilities',headers=h,json={**payload,'name':'Alternate channel available','measurement_type':'Binary','measurement_unit':'yes/no','comparator':'=','required_standard':1,'current_performance':1,'last_validated':'','next_validation':''})
    assert binary.status_code==200,binary.text

    other=client.post('/api/assessments',headers=h,json={'name':'Other Capability Assessment','organization':'Member Client Alpha'}).json()['id']
    cross=client.post('/api/capabilities',headers=h,json={**payload,'assessment_id':other})
    assert cross.status_code==422,cross.text
    h2={**h,'X-Salus-Tenant':'2','X-Salus-User':'Tenant Two User'}
    tenant_cross=client.post('/api/capabilities',headers=h2,json=payload)
    assert tenant_cross.status_code in (403,404),tenant_cross.text

    conn=app.db()
    audit=conn.execute("SELECT * FROM audit_log WHERE entity_type='capabilitie' AND entity_id=? ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
    if audit is None: audit=conn.execute("SELECT * FROM audit_log WHERE entity_id=? AND action='CREATE' ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
    version=conn.execute("SELECT * FROM entity_versions WHERE entity_type='capabilities' AND entity_id=? ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
    package=collect_tenant_records(conn,1);conn.close()
    assert audit and audit['user_name']=='V112 CI'
    assert version and version['version_no']==1
    assert any(x['id']==cid for x in package['capabilities'])
    assert client.get('/health/ready').json()['version']=='1.12.0'
    print('V1_12_OPERATIONAL_CAPABILITY_TARGET_WORKSPACE_PASS',app.DB_BACKEND)


if __name__=='__main__': main()
