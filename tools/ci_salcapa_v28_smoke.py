#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v28.db'))
os.environ.setdefault('SALUS_BACKUP_DIR', str(Path(WORKSPACE.name) / 'backups'))
os.environ.setdefault('SALUS_LOCAL_STORAGE_DIR', str(Path(WORKSPACE.name) / 'attachments'))
os.environ.setdefault('SALUS_AUTH_MODE', 'prototype')
os.environ.setdefault('SALUS_SEED_DEMO', '1')
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app
from portable_backup import collect_tenant_records, replace_tenant_records, validate_records


def post(client, path, headers, payload=None, status=200):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == status, (path, response.status_code, response.text)
    return response.json() if response.content else None


def main():
    client = TestClient(app.app)
    editor = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Profile Editor', 'X-Salus-Tenant': '1'}
    reviewer = {**editor, 'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'Conflict Reviewer'}
    verifier = {**editor, 'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'Credential Verifier'}
    expert = {**editor, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'Assigned Expert'}
    member = {**editor, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Authority'}
    contributor = {**editor, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member User'}

    service_payload = {
        'pillar_code': 'protective', 'name': 'Qualified protective advisory',
        'member_description': 'Provide approved expert advisory support.',
        'internal_scope': 'Controlled qualification, conflict, staffing, and operational details.',
        'default_deliverables': 'Approved advisory summary.',
        'readiness_inputs': 'Qualified expert and independently cleared conflict.',
        'authorization_requirements': 'Member authorization and Salus acceptance.',
        'member_visible': True,
    }
    service = post(client, '/api/salops/catalog/services', editor, service_payload)
    sid = service['id']
    post(client, f'/api/salops/catalog/services/{sid}/transition', editor, {'action': 'Submit', 'reason': 'Ready.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', reviewer, {'action': 'Review', 'reason': 'Reviewed.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', verifier, {'action': 'Approve', 'reason': 'Approved.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', reviewer, {'action': 'Publish', 'reason': 'Published.'})
    request = post(client, '/api/salops/requests', contributor, {
        'assessment_id': 1, 'service_catalog_id': sid, 'title': 'Qualified advisory request',
        'description': 'Request expert support.', 'priority': 'Priority',
    })
    post(client, f"/api/salops/requests/{request['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Member authorization.', 'assigned_to': 'Salus operations'
    })
    engagement = post(client, f"/api/salops/requests/{request['id']}/engagement", editor, {
        'service_type': 'Client value is ignored', 'objective': 'Deliver authorized expert support.',
        'location': 'CONTROLLED LOCATION', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'CONTROLLED ROSTER',
        'communications_plan': 'CONTROLLED COMMS', 'member_status_summary': 'Planning is underway.',
    })
    eid = engagement['id']
    readiness = post(client, f'/api/salops/engagements/{eid}/readiness', editor, {
        'label': 'Expert readiness', 'member_summary': 'Qualified support is being confirmed.',
        'internal_requirement': 'Verify qualification, availability, and conflict clearance.',
        'member_visible': True,
    })

    profile_payload = {
        'expert_actor': 'Assigned Expert', 'member_display_name': 'Jordan Lee',
        'member_role_title': 'Protective Advisory Lead',
        'member_biography': 'Qualified advisor supporting the authorized engagement.',
        'member_contact_summary': 'Coordinate through the approved Salus channel.',
        'internal_biography': 'CONTROLLED PERSONNEL HISTORY AND INTERNAL EXPERIENCE.',
        'disciplines': 'Protective operations; continuity', 'jurisdictions': 'United States',
        'regions': 'Midwest',
    }
    assert client.post('/api/salops/experts', headers=member, json=profile_payload).status_code == 403
    forged_profile = {**profile_payload, 'tenant_id': 2, 'status': 'Active', 'activated_by': 'Client'}
    assert client.post('/api/salops/experts', headers=editor, json=forged_profile).status_code == 422
    profile = post(client, '/api/salops/experts', editor, profile_payload)
    pid = profile['id']
    assert profile['status'] == 'Draft' and profile['profile_key'].startswith('EXP-')
    post(client, f'/api/salops/experts/{pid}/transition', editor, {'action': 'Activate', 'reason': 'Self approval.'}, 409)
    activated = post(client, f'/api/salops/experts/{pid}/transition', reviewer, {'action': 'Activate', 'reason': 'Profile independently approved.'})
    assert activated['status'] == 'Active' and activated['activated_by'] == 'Conflict Reviewer'

    credential_payload = {
        'credential_type': 'Protective operations qualification', 'issuer': 'Qualified Authority',
        'jurisdiction': 'United States', 'effective_on': '2026-01-01', 'expires_on': '2099-12-31',
    }
    forged_credential = {**credential_payload, 'status': 'Verified', 'verified_by': 'Assigned Expert'}
    assert client.post(f'/api/salops/experts/{pid}/credentials', headers=editor, json=forged_credential).status_code == 422
    credential = post(client, f'/api/salops/experts/{pid}/credentials', editor, credential_payload)
    cid = credential['id']
    assert credential['status'] == 'Unverified'
    post(client, f'/api/salops/credentials/{cid}/transition', editor, {'action': 'Verify', 'reason': 'Recorder attempt.'}, 409)
    post(client, f'/api/salops/credentials/{cid}/transition', expert, {'action': 'Verify', 'reason': 'Expert attempt.'}, 403)
    verified = post(client, f'/api/salops/credentials/{cid}/transition', verifier, {'action': 'Verify', 'reason': 'Issuer and qualification independently verified.'})
    assert verified['status'] == 'Verified' and verified['verified_by'] == 'Credential Verifier'

    availability = post(client, f'/api/salops/experts/{pid}/availability', expert, {
        'available_from': '2026-09-09T00:00:00Z', 'available_until': '2026-09-12T00:00:00Z',
        'region': 'Midwest',
    })
    assert availability['status'] == 'Available'
    assert client.post(f'/api/salops/engagements/{eid}/transition', headers=editor, json={
        'status': 'Mobilizing', 'reason': 'Premature.', 'member_status_summary': 'Preparing.'
    }).status_code == 409

    assert client.get(f'/api/salops/engagements/{eid}/conflicts', headers=member).status_code == 403
    conflict = post(client, f'/api/salops/engagements/{eid}/conflicts', expert, {
        'profile_id': pid, 'disclosure': 'No known conflict; independent review requested.'
    })
    conflict_id = conflict['id']
    assert conflict['status'] == 'Pending' and conflict['assessment_id'] == 1
    post(client, f'/api/salops/conflicts/{conflict_id}/review', expert, {
        'decision': 'Cleared', 'reason': 'Self review.'
    }, 403)
    cleared = post(client, f'/api/salops/conflicts/{conflict_id}/review', reviewer, {
        'decision': 'Cleared', 'reason': 'Disclosure independently reviewed and cleared.'
    })
    assert cleared['status'] == 'Cleared'

    forged_assignment = {
        'profile_id': pid, 'conflict_id': conflict_id, 'assignment_role': 'Advisory Lead',
        'member_visible': True, 'status': 'Accepted', 'qualification_snapshot': 'forged',
    }
    assert client.post(f'/api/salops/engagements/{eid}/experts', headers=editor, json=forged_assignment).status_code == 422
    assignment = post(client, f'/api/salops/engagements/{eid}/experts', editor, {
        'profile_id': pid, 'conflict_id': conflict_id, 'assignment_role': 'Advisory Lead', 'member_visible': True,
    })
    aid = assignment['id']
    assert assignment['status'] == 'Proposed' and assignment['member_display_name_snapshot'] == 'Jordan Lee'
    qualification = json.loads(assignment['qualification_snapshot'])
    assert qualification[0]['verified_by'] == 'Credential Verifier'
    post(client, f'/api/salops/expert-assignments/{aid}/transition', editor, {'action': 'Accept', 'reason': 'Wrong actor.'}, 403)
    accepted = post(client, f'/api/salops/expert-assignments/{aid}/transition', expert, {'action': 'Accept', 'reason': 'I accept the governed assignment.'})
    assert accepted['status'] == 'Accepted' and accepted['accepted_by'] == 'Assigned Expert'

    member_experts = client.get(f'/api/salops/engagements/{eid}/experts', headers=member).json()
    assert len(member_experts) == 1 and member_experts[0]['member_display_name_snapshot'] == 'Jordan Lee'
    assert not {'tenant_id', 'profile_id', 'conflict_id', 'qualification_snapshot', 'proposed_by'} & set(member_experts[0])
    assert 'CONTROLLED' not in json.dumps(member_experts)
    assert client.get('/api/salops/experts', headers=member).status_code == 403

    post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Mobilizing', 'reason': 'Qualified assignment accepted.',
        'member_status_summary': 'Authorized support is mobilizing.'
    })
    post(client, f"/api/salops/readiness/{readiness['id']}/transition", reviewer, {
        'status': 'Complete', 'reason': 'Qualification and conflict controls verified.'
    })
    post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Active', 'reason': 'Readiness complete.', 'member_status_summary': 'Authorized support is active.'
    })
    task = post(client, f'/api/salops/engagements/{eid}/tasks', editor, {
        'title': 'Expert advisory briefing', 'instructions': 'Prepare the governed advisory briefing.',
        'assigned_to': 'FORGED ASSIGNEE', 'priority': 'Priority', 'assignment_id': aid,
    })
    assert task['assigned_to'] == 'Assigned Expert' and task['assignment_id'] == aid

    post(client, f'/api/salops/credentials/{cid}/transition', verifier, {'action': 'Withdraw', 'reason': 'Blocked while assigned.'}, 409)
    post(client, f'/api/salops/experts/{pid}/transition', reviewer, {'action': 'Deactivate', 'reason': 'Blocked while assigned.'}, 409)
    post(client, f'/api/salops/expert-assignments/{aid}/transition', expert, {'action': 'Release', 'reason': 'Self release.'}, 403)
    released = post(client, f'/api/salops/expert-assignments/{aid}/transition', editor, {'action': 'Release', 'reason': 'Operational handoff completed.'})
    assert released['status'] == 'Released'
    assert client.get(f'/api/salops/engagements/{eid}/experts', headers=member).json() == []
    withdrawn = post(client, f'/api/salops/credentials/{cid}/transition', verifier, {'action': 'Withdraw', 'reason': 'Qualification retired after release.'})
    inactive = post(client, f'/api/salops/experts/{pid}/transition', reviewer, {'action': 'Deactivate', 'reason': 'Expert is no longer available for assignment.'})
    assert withdrawn['status'] == 'Withdrawn' and inactive['status'] == 'Inactive'

    conn = app.db()
    conn.execute("INSERT INTO tenants(id,name,slug,created_at) VALUES(2,'Other Tenant','other-tenant',?) ON CONFLICT (id) DO NOTHING", (app.now(),))
    conn.commit(); conn.close()
    tenant2 = {**editor, 'X-Salus-Tenant': '2', 'X-Salus-User': 'Other Tenant Operator'}
    post(client, f'/api/salops/experts/{pid}/transition', tenant2, {'action': 'Deactivate', 'reason': 'Cross tenant.'}, 403)

    conn = app.db(); records = collect_tenant_records(conn, 1)
    assert len(records['expert_profiles']) == 1 and len(records['expert_credentials']) == 1
    assert len(records['expert_availability']) == 1 and len(records['expert_conflicts']) == 1
    assert len(records['ops_engagement_assignments']) == 1 and len(records['expert_events']) >= 10
    errors = validate_records(records, 1)
    versions = [r['version_no'] for r in conn.execute("SELECT version_no FROM expert_events WHERE tenant_id=1 AND record_type='expert_assignment' AND record_id=? ORDER BY version_no", (aid,))]
    boundary = conn.execute("SELECT COUNT(*) c FROM security_events WHERE tenant_id=2 AND event_type='EXPERT_TENANT_BOUNDARY_VIOLATION'").fetchone()['c']
    conn.close()
    assert not errors, errors
    assert versions == [1, 2, 3] and boundary == 1
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = {table: conn.execute(f'SELECT COUNT(*) c FROM {table} WHERE tenant_id=1').fetchone()['c'] for table in (
        'expert_profiles', 'expert_credentials', 'expert_availability', 'expert_conflicts', 'ops_engagement_assignments', 'expert_events'
    )}
    conn.close()
    assert restored == {'expert_profiles': 1, 'expert_credentials': 1, 'expert_availability': 1, 'expert_conflicts': 1, 'ops_engagement_assignments': 1, 'expert_events': len(records['expert_events'])}
    print('SALCAPA_V28_EXPERT_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
