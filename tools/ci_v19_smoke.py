#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND']='sqlite'
os.environ['SALUS_DB_PATH']=str(Path(TMP.name)/'v19-smoke.db')
os.environ['SALUS_AUTH_MODE']='prototype'

from starlette.testclient import TestClient
import sys
sys.path.insert(0,str(ROOT))
import app
from portable_backup import collect_tenant_records

def main():
    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V19 CI','X-Salus-Tenant':'1'}
    empty=client.get('/api/intake',headers=h)
    assert empty.status_code==200,empty.text
    assert empty.json()['metrics']=={'total':0,'evidenceLeads':0,'discoveries':0,'decisionInputs':0}

    payload={'recordType':'Evidence Lead','title':'Generator runtime record','details':'Runtime observation requires governed evidence review.','sourceContext':'V19 controlled lifecycle smoke'}
    created=client.post('/api/intake',headers=h,json=payload)
    assert created.status_code==200,created.text
    record=created.json()['record']
    assert record['id'].startswith('INT-') and record['status']=='Draft' and record['version']==1
    assert record['createdByName']=='V19 CI'

    listed=client.get('/api/intake',headers=h).json()
    assert listed['metrics']=={'total':1,'evidenceLeads':1,'discoveries':0,'decisionInputs':0}
    assert listed['records'][0]['id']==record['id']
    assert 'created_by_email' not in listed['records'][0]

    forged=client.post('/api/intake',headers=h,json={**payload,'status':'Approved'})
    assert forged.status_code==422,forged.text
    assert client.post('/api/intake',headers=h,json={**payload,'title':'x'*161}).status_code==422
    assert client.post('/api/intake',headers=h,json={**payload,'details':'   '}).status_code==422
    assert client.put('/api/governed_intake/1',headers=h,json={'status':'Approved'}).status_code==404
    assert client.delete('/api/governed_intake/1',headers=h).status_code==404

    conn=app.db()
    audit=conn.execute("SELECT * FROM audit_log WHERE entity_type='governed_intake' ORDER BY id DESC LIMIT 1").fetchone()
    assert audit and audit['action']=='CREATE' and audit['tenant_id']==1
    package=collect_tenant_records(conn,1)
    assert len(package['governed_intake'])==1 and package['governed_intake'][0]['record_key']==record['id']
    conn.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)",('Tenant Two','tenant-two','Active',app.now()))
    conn.commit(); conn.close()

    h2={**h,'X-Salus-Tenant':'2','X-Salus-User':'Tenant Two User'}
    assert client.get('/api/intake',headers=h2).json()['metrics']['total']==0
    assert client.post('/api/intake',headers=h2,json={**payload,'recordType':'Discovery','title':'Tenant two record'}).status_code==200
    assert client.get('/api/intake',headers=h).json()['metrics']['total']==1
    assert client.get('/api/intake',headers=h2).json()['metrics']['total']==1
    assert client.get('/health/ready').json()['version']=='1.9.0'
    print('V1_9_GOVERNED_INTAKE_PASS',app.DB_BACKEND)

if __name__=='__main__':
    main()
