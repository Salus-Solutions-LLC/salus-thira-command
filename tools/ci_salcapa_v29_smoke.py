#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
WORKSPACE=tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND','sqlite')
os.environ.setdefault('SALUS_DB_PATH',str(Path(WORKSPACE.name)/'salcapa-v29.db'))
os.environ.setdefault('SALUS_BACKUP_DIR',str(Path(WORKSPACE.name)/'backups'))
os.environ.setdefault('SALUS_LOCAL_STORAGE_DIR',str(Path(WORKSPACE.name)/'attachments'))
os.environ.setdefault('SALUS_AUTH_MODE','prototype')
os.environ.setdefault('SALUS_SEED_DEMO','1')
sys.path.insert(0,str(ROOT))

from fastapi.testclient import TestClient
import app
from portable_backup import collect_tenant_records, replace_tenant_records, validate_records

def post(client,path,headers,payload,status=200):
    response=client.post(path,headers=headers,json=payload)
    assert response.status_code==status,(path,response.status_code,response.text)
    return response.json() if response.content else None

def payload(name='Healthcare readiness',guidance='Healthcare advisory starting point'):
    return {
        'industry_code':'healthcare-ems-public-health','name':name,
        'member_summary':'Healthcare-specific advisory context for readiness work.',
        'internal_rationale':'CONTROLLED INDUSTRY RATIONALE AND REFERENCE ANALYSIS.',
        'items':[
            {'item_type':'Terminology','item_key':'patient-surge','member_label':'Patient surge','member_guidance':'Use consistent surge terminology.','internal_definition':'CONTROLLED DEFINITION.','reference_metadata':'','default_payload':{},'member_visible':True,'sort_order':10},
            {'item_type':'Capability','item_key':'clinical-continuity','member_label':'Clinical continuity','member_guidance':'Assess continuity outcomes.','internal_definition':'CONTROLLED CAPABILITY BASIS.','reference_metadata':'','default_payload':{},'member_visible':True,'sort_order':20},
            {'item_type':'Scenario','item_key':'mass-casualty','member_label':'Mass casualty','member_guidance':'Consider sustained demand.','internal_definition':'CONTROLLED SCENARIO LOGIC.','reference_metadata':'','default_payload':{},'member_visible':True,'sort_order':30},
            {'item_type':'Regulatory Reference','item_key':'applicable-obligations','member_label':'Applicable obligations','member_guidance':'Validate applicability with qualified counsel.','internal_definition':'NO COMPLIANCE CONCLUSION.','reference_metadata':'CONTROLLED REFERENCE LOCATOR.','default_payload':{},'member_visible':True,'sort_order':40},
            {'item_type':'Service Default','item_key':'readiness-advisory','member_label':'Readiness advisory','member_guidance':guidance,'internal_definition':'CONTROLLED SERVICE BASIS.','reference_metadata':'','default_payload':{'pillar':'readiness','advisory':guidance},'member_visible':True,'sort_order':50},
            {'item_type':'Service Default','item_key':'internal-only','member_label':'Internal planning default','member_guidance':'','internal_definition':'CONTROLLED INTERNAL DEFAULT.','reference_metadata':'','default_payload':{'internal':'CONTROLLED'},'member_visible':False,'sort_order':60},
        ],
    }

def main():
    client=TestClient(app.app)
    editor={'X-Salus-Tenant':'1','X-Salus-Role':'Assessment Director','X-Salus-User':'Profile Editor'}
    reviewer={**editor,'X-Salus-Role':'Program Owner','X-Salus-User':'Independent Reviewer'}
    approver={**editor,'X-Salus-Role':'System Administrator','X-Salus-User':'Independent Approver'}
    publisher={**editor,'X-Salus-User':'Publication Authority'}
    member={**editor,'X-Salus-Role':'Contributor','X-Salus-User':'Protected Member'}

    assert client.post('/api/industry-profiles',headers=member,json=payload()).status_code==403
    forged={**payload(),'status':'Published','tenant_id':2,'published_by':'client'}
    assert client.post('/api/industry-profiles',headers=editor,json=forged).status_code==422
    duplicate=payload(); duplicate['items'].append(dict(duplicate['items'][0]))
    assert client.post('/api/industry-profiles',headers=editor,json=duplicate).status_code==422

    profile=post(client,'/api/industry-profiles',editor,payload())
    profile_id=profile['id']
    assert profile['status']=='Draft' and profile['version_no']==1
    post(client,f'/api/industry-profiles/{profile_id}/transition',editor,{'action':'Submit','reason':'Ready for independent review.'})
    post(client,f'/api/industry-profiles/{profile_id}/transition',editor,{'action':'Review','reason':'Self review.'},409)
    post(client,f'/api/industry-profiles/{profile_id}/transition',reviewer,{'action':'Review','reason':'Content independently reviewed.'})
    post(client,f'/api/industry-profiles/{profile_id}/transition',reviewer,{'action':'Approve','reason':'Reviewer self approval.'},409)
    post(client,f'/api/industry-profiles/{profile_id}/transition',approver,{'action':'Approve','reason':'Profile independently approved.'})
    published=post(client,f'/api/industry-profiles/{profile_id}/transition',publisher,{'action':'Publish','reason':'Approved profile published.'})
    assert published['status']=='Published'
    selected=post(client,'/api/industry-configurations',approver,{'profile_id':profile_id})
    assert selected['status']=='Active' and selected['profile_version_snapshot']==1

    assessment_payload={'name':'Industry-aware assessment','organization':'Member organization','industry_profile_id':profile_id,'assessment_type':'Enterprise','purpose':'Evaluate readiness.','mission':'Protect patient care.','scope':'Enterprise operations.','exclusions':'','executive_sponsor':'','assessment_director':'','lead_assessor':'','start_date':'','target_completion':'','reassessment_date':'','classification':'Standard'}
    assessment=post(client,'/api/assessments',member,assessment_payload)
    assessment_id=assessment['id']
    assert assessment['industry_profile_name_snapshot']=='Healthcare readiness'
    assert 'industry_defaults_snapshot_json' not in assessment and 'industry_profile_applied_by' not in assessment

    service=post(client,'/api/salops/catalog/services',editor,{
        'pillar_code':'readiness','name':'Healthcare readiness advisory','member_description':'Industry-aware readiness support.',
        'internal_scope':'Controlled delivery scope.','default_deliverables':'Approved readiness summary.',
        'readiness_inputs':'Authorized scope and member contact.','authorization_requirements':'Member authorization.',
        'industry_profile_id':profile_id,'member_visible':True,
    })
    assert service['industry_profile_version_snapshot']==1
    defaults=json.loads(service['industry_defaults_snapshot_json'])
    assert len(defaults)==2 and defaults[1]['payload']['internal']=='CONTROLLED'

    member_profiles=client.get('/api/industry-profiles',headers=member).json()
    assert len(member_profiles)==1 and len(member_profiles[0]['items'])==5
    assert 'internal_rationale' not in member_profiles[0]
    assert 'CONTROLLED' not in json.dumps(member_profiles)
    member_assessment=next(r for r in client.get('/api/assessments',headers=member).json() if r['id']==assessment_id)
    assert not {'industry_defaults_snapshot_json','industry_profile_applied_by'} & set(member_assessment)
    forged_update={'industry_profile_id':None,'industry_profile_name_snapshot':'Forged','industry_defaults_snapshot_json':'{}'}
    assert client.put(f'/api/assessments/{assessment_id}',headers=member,json=forged_update).status_code==409

    revision=post(client,f'/api/industry-profiles/{profile_id}/revise',editor,payload('Healthcare readiness revised','Revised advisory starting point'))
    revision_id=revision['id']; assert revision['version_no']==2 and revision['supersedes_id']==profile_id
    for headers,action in ((editor,'Submit'),(reviewer,'Review'),(approver,'Approve'),(publisher,'Publish')):
        post(client,f'/api/industry-profiles/{revision_id}/transition',headers,{'action':action,'reason':f'{action} revision.'})
    before_selection=post(client,'/api/assessments',editor,{**assessment_payload,'name':'Pinned old profile'})
    assert before_selection['industry_profile_version_snapshot']==1
    post(client,'/api/industry-configurations',approver,{'profile_id':revision_id})
    after_selection=post(client,'/api/assessments',editor,{**assessment_payload,'name':'Pinned revised profile','industry_profile_id':revision_id})
    assert after_selection['industry_profile_version_snapshot']==2
    conn=app.db()
    original=conn.execute('SELECT industry_profile_version_snapshot,industry_defaults_snapshot_json FROM assessments WHERE id=?',(assessment_id,)).fetchone()
    assert original['industry_profile_version_snapshot']==1 and 'Healthcare advisory starting point' in original['industry_defaults_snapshot_json']
    assert conn.execute('SELECT COUNT(*) c FROM threats WHERE assessment_id=?',(assessment_id,)).fetchone()['c']==0
    assert conn.execute('SELECT COUNT(*) c FROM evidence WHERE assessment_id=?',(assessment_id,)).fetchone()['c']==0
    records=collect_tenant_records(conn,1); errors=validate_records(records,1)
    versions=[r['version_no'] for r in conn.execute('SELECT version_no FROM industry_profile_events WHERE profile_id=? ORDER BY version_no',(profile_id,))]
    conn.execute("INSERT INTO tenants(id,name,slug,status,created_at) VALUES(2,'Other Tenant','other-tenant','Active',?) ON CONFLICT(id) DO NOTHING",(app.now(),)); conn.commit(); conn.close()
    assert not errors,errors
    assert versions==[1,2,3,4,5,6]
    tenant2={**editor,'X-Salus-Tenant':'2','X-Salus-User':'Other Tenant'}
    post(client,f'/api/industry-profiles/{profile_id}/transition',tenant2,{'action':'Retire','reason':'Cross tenant.'},403)
    conn=app.db(); boundary=conn.execute("SELECT COUNT(*) c FROM security_events WHERE tenant_id=2 AND event_type='INDUSTRY_PROFILE_TENANT_BOUNDARY_VIOLATION'").fetchone()['c']; conn.close(); assert boundary==1

    conn=app.db(); replace_tenant_records(conn,1,records); conn.commit()
    restored={table:conn.execute(f'SELECT COUNT(*) c FROM {table} WHERE tenant_id=1').fetchone()['c'] for table in ('industry_profiles','industry_profile_items','industry_profile_events','tenant_industry_configurations')}; conn.close()
    assert restored=={table:len(records[table]) for table in restored}
    print('SALCAPA_V29_INDUSTRY_PROFILES_PASS',app.DB_BACKEND)

if __name__=='__main__': main()
