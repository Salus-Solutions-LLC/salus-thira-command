#!/usr/bin/env python3
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND']='sqlite'
os.environ['SALUS_DB_PATH']=str(Path(TMP.name)/'v114-smoke.db')
os.environ['SALUS_AUTH_MODE']='prototype'
sys.path.insert(0,str(ROOT))
from starlette.testclient import TestClient
import app
from portable_backup import collect_tenant_records


def post(client,path,headers,payload):
    response=client.post(path,headers=headers,json=payload)
    assert response.status_code==200,(path,response.status_code,response.text)
    return response.json()


def main():
    client=TestClient(app.app)
    h={'X-Salus-Role':'Assessment Director','X-Salus-User':'V114 CI','X-Salus-Tenant':'1','X-Salus-Clearance':'Highly Sensitive'}
    aid=post(client,'/api/assessments',h,{'name':'V114 Gap and Improvement Assessment','organization':'Member Client Alpha'})['id']
    other_aid=post(client,'/api/assessments',h,{'name':'V114 Boundary Assessment','organization':'Member Client Alpha'})['id']
    threat=post(client,'/api/threats',h,{'assessment_id':aid,'name':'Capability disruption','category':'Operational'})
    scenario=post(client,'/api/scenarios',h,{'assessment_id':aid,'threat_id':threat['id'],'title':'Capability disruption scenario','narrative':'A governed scenario requiring measurable improvement.'})
    capability=post(client,'/api/capabilities',h,{'assessment_id':aid,'scenario_id':scenario['id'],'name':'Continuity capability','required_outcome':'Restore priority service.','measurement_type':'Percentage','measurement_unit':'%','comparator':'>=','required_standard':95,'current_performance':60})
    other_capability=post(client,'/api/capabilities',h,{'assessment_id':other_aid,'name':'Boundary capability','required_outcome':'Remain isolated.','measurement_type':'Percentage','measurement_unit':'%','comparator':'>=','required_standard':100,'current_performance':50})

    gap_payload={'assessment_id':aid,'capability_id':capability['id'],'gap_type':'Continuity','description':'Demonstrated recovery is below the required standard.','severity':'High','root_cause':'Single recovery path and incomplete exercises.','owner':'Continuity Director'}
    gap=post(client,'/api/gaps',h,gap_payload)
    assert gap['status']=='Open' and gap['owner']=='Continuity Director'
    for key,value in {'status':'Closed','tenant_id':2,'created_at':'2000-01-01T00:00:00Z','updated_at':'2000-01-01T00:00:00Z','version':99}.items():
        response=client.post('/api/gaps',headers=h,json={**gap_payload,key:value})
        assert response.status_code==422,(key,response.text)
    assert client.post('/api/gaps',headers=h,json={**gap_payload,'capability_id':other_capability['id']}).status_code==422
    assert client.post('/api/gaps',headers=h,json={**gap_payload,'severity':'Extreme'}).status_code==422
    assert client.put(f'/api/gaps/{gap["id"]}',headers=h,json={'status':'Closed'}).status_code==409
    assert client.put(f'/api/gaps/{gap["id"]}',headers=h,json={'updated_at':'2000-01-01T00:00:00Z'}).status_code==409
    updated=client.put(f'/api/gaps/{gap["id"]}',headers=h,json={'severity':'Critical','owner':'Recovery Executive'})
    assert updated.status_code==200 and updated.json()['severity']=='Critical' and updated.json()['owner']=='Recovery Executive'
    gap=post(client,f'/api/gaps/{gap["id"]}/transition',h,{'status':'Under Review','reason':'Root-cause analysis is ready for accountable review.'})
    gap=post(client,f'/api/gaps/{gap["id"]}/transition',h,{'status':'Mitigating','reason':'An approved improvement is now addressing the gap.'})
    assert gap['status']=='Mitigating'

    improvement_payload={'assessment_id':aid,'gap_id':gap['id'],'title':'Add an independent recovery path','description':'Implement and exercise a second recovery path.','initial_cost':125000,'recurring_cost':18000,'implementation_days':120,'feasibility':4,'consequence_reduction':5,'mission_benefit':5,'sustainability':4,'compliance_impact':4,'staffing_impact':3,'expected_capability_gain':35,'dependencies':'Recovery vendor and exercise window.','owner':'Recovery Program Owner'}
    improvement=post(client,'/api/improvements',h,improvement_payload)
    iid=improvement['id']; initial_priority=improvement['priority_score']
    assert improvement['status']=='Proposed' and improvement['validation_status']=='Pending' and 0<initial_priority<=100
    for key,value in {'status':'Complete','priority_score':100,'validation_status':'Validated','validation_evidence_id':1,'validated_by':'forged','validated_at':'2000-01-01T00:00:00Z','tenant_id':2,'created_at':'2000-01-01T00:00:00Z'}.items():
        response=client.post('/api/improvements',headers=h,json={**improvement_payload,key:value})
        assert response.status_code==422,(key,response.text)
    assert client.post('/api/improvements',headers=h,json={**improvement_payload,'gap_id':999999}).status_code==422
    assert client.post('/api/improvements',headers=h,json={**improvement_payload,'feasibility':6}).status_code==422
    for forged in ({'status':'Complete'},{'priority_score':100},{'validation_status':'Validated'},{'validated_by':'forged'},{'updated_at':'2000-01-01T00:00:00Z'}):
        response=client.put(f'/api/improvements/{iid}',headers=h,json=forged)
        assert response.status_code==409,(forged,response.text)
    reprioritized=client.put(f'/api/improvements/{iid}',headers=h,json={'initial_cost':10000,'implementation_days':25})
    assert reprioritized.status_code==200 and reprioritized.json()['priority_score']>initial_priority

    transitions=[('Under Review','Alternatives and dependencies were reviewed.'),('Approved','The accountable authority approved implementation.'),('In Progress','Funding and implementation resources were released.'),('Complete','Implementation deliverables were completed and require capability validation.')]
    for target,reason in transitions:
        improvement=post(client,f'/api/improvements/{iid}/transition',h,{'status':target,'reason':reason})
        assert improvement['status']==target
    duplicate=client.post(f'/api/improvements/{iid}/transition',headers=h,json={'status':'Complete','reason':'Attempt duplicate completion.'})
    assert duplicate.status_code==409
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    completion=[x for x in triggers if x['source']=='Completed Improvement' and x['trigger_type']=='Capability Validation' and x['affected_record_id']==iid]
    assert len(completion)==1 and completion[0]['status']=='Open',completion

    future=(date.today()+timedelta(days=365)).isoformat()
    pending=post(client,'/api/evidence',h,{'assessment_id':aid,'capability_id':capability['id'],'scenario_id':scenario['id'],'title':'Pending validation record','verification_status':'Pending','valid_until':future})
    denied=client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':pending['id'],'validation_status':'Validated','validation_outcome':'Not eligible.','validated_effectiveness_percent':100})
    assert denied.status_code==409
    other_evidence=post(client,'/api/evidence',h,{'assessment_id':other_aid,'capability_id':other_capability['id'],'title':'Boundary validation record','verification_status':'Verified','valid_until':future})
    denied=client.post(f'/api/improvements/{iid}/validate',headers=h,json={'evidence_id':other_evidence['id'],'validation_status':'Validated','validation_outcome':'Wrong assessment.','validated_effectiveness_percent':100})
    assert denied.status_code==422
    evidence=post(client,'/api/evidence',h,{'assessment_id':aid,'capability_id':capability['id'],'scenario_id':scenario['id'],'title':'Recovery exercise validation','evidence_type':'Exercise Result','source':'Controlled recovery exercise','owner':'Independent Evaluator','evidence_date':date.today().isoformat(),'reliability':'High','verification_status':'Verified','valid_until':future,'notes':'Observed restoration against the target.'})
    validated=post(client,f'/api/improvements/{iid}/validate',h,{'evidence_id':evidence['id'],'validation_status':'Partially Validated','validation_outcome':'Exercise demonstrated 82% of the expected effectiveness.','validated_effectiveness_percent':82})
    assert validated['validation_status']=='Partially Validated' and validated['validation_evidence_id']==evidence['id'] and validated['validated_by']=='V114 CI'
    triggers=client.get(f'/api/reassessment_triggers?assessment_id={aid}',headers=h).json()
    completion=[x for x in triggers if x['source']=='Completed Improvement' and x['affected_record_id']==iid]
    assert len(completion)==1 and completion[0]['status']=='Resolved'

    conn=app.db()
    gap_audits=[dict(x) for x in conn.execute("SELECT * FROM audit_log WHERE entity_id=? AND action='GAP_TRANSITION' ORDER BY id",(gap['id'],))]
    improvement_audits=[dict(x) for x in conn.execute("SELECT * FROM audit_log WHERE entity_id=? AND action IN ('IMPROVEMENT_TRANSITION','VALIDATE') ORDER BY id",(iid,))]
    gap_versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='gaps' AND entity_id=? ORDER BY version_no",(gap['id'],))]
    improvement_versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='improvements' AND entity_id=? ORDER BY version_no",(iid,))]
    trigger_versions=[dict(x) for x in conn.execute("SELECT * FROM entity_versions WHERE entity_type='reassessment_triggers' AND entity_id=? ORDER BY version_no",(completion[0]['id'],))]
    package=collect_tenant_records(conn,1);conn.close()
    assert len(gap_audits)==2 and len(gap_versions)>=4
    assert len([x for x in improvement_audits if x['action']=='IMPROVEMENT_TRANSITION'])==4
    assert any(x['action']=='VALIDATE' for x in improvement_audits) and len(improvement_versions)>=7
    assert len(trigger_versions)>=2
    assert any(x['id']==gap['id'] and x['owner']=='Recovery Executive' for x in package['gaps'])
    assert any(x['id']==iid and x['validation_status']=='Partially Validated' for x in package['improvements'])
    assert client.get('/health/ready').json()['version']=='1.14.0'
    print('V1_14_OPERATIONAL_GAP_IMPROVEMENT_WORKSPACE_PASS',app.DB_BACKEND)


if __name__=='__main__': main()
