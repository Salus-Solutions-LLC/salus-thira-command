#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v27.db'))
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
    editor = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Catalog Editor', 'X-Salus-Tenant': '1'}
    reviewer = {**editor, 'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'Catalog Reviewer'}
    approver = {**editor, 'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'Catalog Approver'}
    member = {**editor, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Authority'}
    contributor = {**editor, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member User'}

    pillars = client.get('/api/salops/catalog/pillars', headers=member).json()
    assert [x['pillar_code'] for x in pillars] == ['readiness', 'protective', 'incident', 'recovery']
    assert client.get('/api/salops/catalog/services', headers=member).json() == []

    service_payload = {
        'pillar_code': 'protective',
        'name': 'Protective operations planning',
        'member_description': 'Plan and coordinate approved protective support.',
        'internal_scope': 'Controlled tactics, staffing assumptions, vendors, locations, and communications.',
        'default_deliverables': 'Approved operating plan; member-safe status updates; completion summary.',
        'readiness_inputs': 'Authority confirmation; protected-person requirements; controlled logistics review.',
        'authorization_requirements': 'Protected Member authorization and Salus operational acceptance.',
        'member_visible': True,
    }
    assert client.post('/api/salops/catalog/services', headers=member, json=service_payload).status_code == 403
    forged = {**service_payload, 'tenant_id': 2, 'status': 'Published', 'version_no': 99}
    assert client.post('/api/salops/catalog/services', headers=editor, json=forged).status_code == 422
    service = post(client, '/api/salops/catalog/services', editor, service_payload)
    assert service['status'] == 'Draft' and service['version_no'] == 1 and service['service_key'].startswith('SVC-')
    sid = service['id']
    assert client.post('/api/salops/requests', headers=contributor, json={
        'assessment_id': 1, 'service_catalog_id': sid, 'title': 'Premature request', 'priority': 'Priority'
    }).status_code == 409

    post(client, f'/api/salops/catalog/services/{sid}/transition', editor, {'action': 'Submit', 'reason': 'Ready for independent review.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', editor, {'action': 'Review', 'reason': 'Self review attempt.'}, 409)
    post(client, f'/api/salops/catalog/services/{sid}/transition', reviewer, {'action': 'Review', 'reason': 'Scope and member boundary reviewed.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', reviewer, {'action': 'Approve', 'reason': 'Same-person approval attempt.'}, 409)
    post(client, f'/api/salops/catalog/services/{sid}/transition', approver, {'action': 'Approve', 'reason': 'Authority and readiness requirements approved.'})
    post(client, f'/api/salops/catalog/services/{sid}/transition', editor, {'action': 'Publish', 'reason': 'Editor publish attempt.'}, 409)
    published = post(client, f'/api/salops/catalog/services/{sid}/transition', reviewer, {'action': 'Publish', 'reason': 'Approved for member use.'})
    assert published['status'] == 'Published'

    member_catalog = client.get('/api/salops/catalog/services', headers=member).json()
    assert len(member_catalog) == 1 and member_catalog[0]['id'] == sid
    assert not {'tenant_id', 'internal_scope', 'readiness_inputs', 'created_by', 'last_material_editor', 'published_by'} & set(member_catalog[0])
    assert 'Controlled tactics' not in json.dumps(member_catalog)
    history = client.get(f'/api/salops/catalog/services/{sid}/history', headers=editor).json()
    assert [x['version_no'] for x in history] == list(range(1, len(history) + 1))
    assert client.get(f'/api/salops/catalog/services/{sid}/history', headers=member).status_code == 403

    forged_request = {
        'assessment_id': 1, 'service_catalog_id': sid, 'title': 'Protective support request',
        'description': 'Request authorized planning.', 'priority': 'Priority',
        'service_version_snapshot': 99, 'status': 'Authorized', 'tenant_id': 2,
    }
    assert client.post('/api/salops/requests', headers=contributor, json=forged_request).status_code == 422
    request = post(client, '/api/salops/requests', contributor, {
        'assessment_id': 1, 'service_catalog_id': sid, 'title': 'Protective support request',
        'description': 'Request authorized planning.', 'priority': 'Priority',
    })
    assert request['status'] == 'Requested' and request['service_catalog_id'] == sid
    assert request['service_version_snapshot'] == 1 and request['service_name_snapshot'] == service_payload['name']
    request_snapshot = {k: request[k] for k in ('service_key_snapshot', 'service_version_snapshot', 'service_name_snapshot', 'service_member_description_snapshot', 'service_deliverables_snapshot')}

    revision_payload = {**service_payload, 'name': 'Protective operations coordination', 'member_description': 'Coordinate approved protective support from planning through completion.'}
    revision = post(client, f'/api/salops/catalog/services/{sid}/revise', editor, revision_payload)
    assert revision['version_no'] == 2 and revision['supersedes_id'] == sid and revision['status'] == 'Draft'
    rid = revision['id']
    post(client, f'/api/salops/catalog/services/{rid}/transition', editor, {'action': 'Submit', 'reason': 'Updated definition ready.'})
    post(client, f'/api/salops/catalog/services/{rid}/transition', reviewer, {'action': 'Review', 'reason': 'Revision reviewed.'})
    post(client, f'/api/salops/catalog/services/{rid}/transition', approver, {'action': 'Approve', 'reason': 'Revision approved.'})
    post(client, f'/api/salops/catalog/services/{rid}/transition', reviewer, {'action': 'Publish', 'reason': 'Revision published.'})
    internal_catalog = client.get('/api/salops/catalog/services', headers=editor).json()
    assert next(x for x in internal_catalog if x['id'] == sid)['status'] == 'Superseded'
    assert [x['id'] for x in client.get('/api/salops/catalog/services', headers=member).json()] == [rid]
    persisted_request = next(x for x in client.get('/api/salops/requests', headers=member).json() if x['id'] == request['id'])
    assert all(persisted_request[k] == v for k, v in request_snapshot.items())

    tenant2 = {**editor, 'X-Salus-Tenant': '2', 'X-Salus-User': 'Other Tenant Operator'}
    conn = app.db()
    conn.execute("INSERT INTO tenants(id,name,slug,created_at) VALUES(2,'Other Tenant','other-tenant',?)", (app.now(),))
    conn.commit(); conn.close()
    assert client.post(f'/api/salops/catalog/services/{rid}/transition', headers=tenant2, json={'action': 'Retire', 'reason': 'Cross tenant'}).status_code == 403

    post(client, f"/api/salops/requests/{request['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Member authority approves this service.', 'assigned_to': 'Salus operations'
    })
    assert client.post(f"/api/salops/requests/{request['id']}/engagement", headers=member, json={
        'service_type': 'Forged', 'objective': 'Forged', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'Forged',
        'communications_plan': 'Forged', 'member_status_summary': 'Forged',
    }).status_code == 403
    engagement = post(client, f"/api/salops/requests/{request['id']}/engagement", editor, {
        'service_type': 'Client-forged service label', 'objective': 'Coordinate the authorized protective support.',
        'location': 'CONTROLLED LOCATION', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'CONTROLLED ROSTER',
        'communications_plan': 'CONTROLLED COMMS', 'member_status_summary': 'Planning is underway.',
    })
    eid = engagement['id']
    assert engagement['service_type'] == request_snapshot['service_name_snapshot']
    assert engagement['service_version_snapshot'] == request_snapshot['service_version_snapshot']
    post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Mobilizing', 'reason': 'Premature mobilization.', 'member_status_summary': 'Preparing.'
    }, 409)

    visible = post(client, f'/api/salops/engagements/{eid}/readiness', editor, {
        'label': 'Member authority confirmed', 'member_summary': 'Member authorization confirmed.',
        'internal_requirement': 'Validate authority record and controlled duty-of-care conditions.',
        'member_visible': True, 'due_at': '2026-09-09T12:00:00Z',
    })
    hidden = post(client, f'/api/salops/engagements/{eid}/readiness', editor, {
        'label': 'Controlled staffing check', 'member_summary': 'Internal readiness review.',
        'internal_requirement': 'Validate protected roster, vendors, locations, credentials, and tactics.',
        'member_visible': False,
    })
    assert client.post(f'/api/salops/engagements/{eid}/readiness', headers=member, json={
        'label': 'Forged readiness', 'member_summary': 'Forged', 'internal_requirement': 'Forged'
    }).status_code == 403
    member_readiness = client.get(f'/api/salops/engagements/{eid}/readiness', headers=member).json()
    assert [x['id'] for x in member_readiness] == [visible['id']]
    assert 'internal_requirement' not in member_readiness[0]
    assert 'protected roster' not in json.dumps(member_readiness).lower()

    post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Mobilizing', 'reason': 'Readiness requirements documented.', 'member_status_summary': 'Mobilization readiness is being confirmed.'
    })
    post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Active', 'reason': 'Pending readiness attempt.', 'member_status_summary': 'Preparing to begin.'
    }, 409)
    post(client, f"/api/salops/readiness/{visible['id']}/transition", reviewer, {'status': 'Complete', 'reason': 'Authority record verified.'})
    post(client, f"/api/salops/readiness/{hidden['id']}/transition", reviewer, {'status': 'Exception', 'reason': 'Authorized exception documented with compensating control.'})
    active = post(client, f'/api/salops/engagements/{eid}/transition', editor, {
        'status': 'Active', 'reason': 'All readiness items resolved.', 'member_status_summary': 'Authorized service delivery is active.'
    })
    assert active['engagement']['status'] == 'Active'
    member_engagement = next(x for x in client.get('/api/salops/engagements', headers=member).json() if x['id'] == eid)
    assert member_engagement['readiness_summary'] == {'pending': 0, 'complete': 1, 'exceptions': 1, 'total': 2}
    assert not {'location', 'operational_lead', 'communications_plan', 'service_member_scope_snapshot'} & set(member_engagement)

    conn = app.db(); records = collect_tenant_records(conn, 1)
    assert len(records['ops_service_pillars']) == 4
    assert len(records['ops_service_catalog']) == 2 and len(records['ops_engagement_readiness']) == 2
    errors = validate_records(records, 1)
    boundary_events = conn.execute("SELECT COUNT(*) c FROM security_events WHERE tenant_id=2 AND event_type='SALOPS_CATALOG_TENANT_BOUNDARY_VIOLATION'").fetchone()['c']
    audit_tenants = {r['tenant_id'] for r in conn.execute("SELECT tenant_id FROM audit_log WHERE entity_type IN ('ops_service_catalog','ops_engagement_readiness')")}
    conn.close()
    assert not errors, errors
    assert boundary_events == 1 and audit_tenants == {1}
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = {
        'pillars': conn.execute('SELECT COUNT(*) c FROM ops_service_pillars WHERE tenant_id=1').fetchone()['c'],
        'services': conn.execute('SELECT COUNT(*) c FROM ops_service_catalog WHERE tenant_id=1').fetchone()['c'],
        'events': conn.execute('SELECT COUNT(*) c FROM ops_catalog_events WHERE tenant_id=1').fetchone()['c'],
        'readiness': conn.execute('SELECT COUNT(*) c FROM ops_engagement_readiness WHERE tenant_id=1').fetchone()['c'],
    }
    conn.close()
    assert restored['pillars'] == 4 and restored['services'] == 2 and restored['events'] >= 9 and restored['readiness'] == 2
    print('SALCAPA_V27_CATALOG_ORCHESTRATION_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
