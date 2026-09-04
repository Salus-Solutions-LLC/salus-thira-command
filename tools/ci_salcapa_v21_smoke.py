#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v21.db'))
os.environ.setdefault('SALUS_BACKUP_DIR', str(Path(WORKSPACE.name) / 'backups'))
os.environ.setdefault('SALUS_LOCAL_STORAGE_DIR', str(Path(WORKSPACE.name) / 'attachments'))
os.environ.setdefault('SALUS_AUTH_MODE', 'prototype')
os.environ.setdefault('SALUS_SEED_DEMO', '1')
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
import app


def post(client, path, headers, payload=None, status=200):
    response = client.post(path, headers=headers, json=payload)
    assert response.status_code == status, (path, response.status_code, response.text)
    return response.json() if response.content else None


def main():
    client = TestClient(app.app)
    director = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Report Director', 'X-Salus-Tenant': '1'}
    lead = {**director, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'Independent Reviewer'}
    member = {**director, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Executive'}
    contributor = {**director, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member Contributor'}
    admin_requester = {**director, 'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'Recovery Requester'}
    admin_authority = {**admin_requester, 'X-Salus-User': 'Recovery Authority'}

    forged = client.post('/api/reports/1', headers=director, json={'status': 'Released', 'tenant_id': 2})
    assert forged.status_code == 422
    assert client.post('/api/reports/1', headers=contributor).status_code == 403

    report = post(client, '/api/reports/1', director)
    report_id = report['id']
    assert report['status'] == 'Draft' and report['created_by'] == 'Report Director'
    assert client.put(f'/api/report_versions/{report_id}', headers=director, json={'status': 'Released'}).status_code == 404
    assert post(client, f'/api/reports/versions/{report_id}/transition', member, {'status': 'Reviewed', 'reason': 'Attempted member review'}, 403)
    assert post(client, f'/api/reports/versions/{report_id}/transition', lead, {'status': 'Reviewed', 'reason': 'Independent content and provenance review'})['reviewed_by'] == 'Independent Reviewer'
    assert post(client, f'/api/reports/versions/{report_id}/transition', member, {'status': 'Approved', 'reason': 'Protected Member executive approval'})['approved_by'] == 'Protected Member Executive'
    assert post(client, f'/api/reports/versions/{report_id}/transition', lead, {'status': 'Released', 'reason': 'Attempted assessor release'}, 403)
    released = post(client, f'/api/reports/versions/{report_id}/transition', director, {'status': 'Released', 'reason': 'Authorized issuance'})
    assert released['released_by'] == 'Report Director'
    assert post(client, f'/api/reports/versions/{report_id}/transition', director, {'status': 'Reviewed', 'reason': 'Attempted rewrite'}, 409)

    snapshot = client.get(f'/api/reports/versions/{report_id}/snapshot', headers=member)
    assert snapshot.status_code == 200 and snapshot.headers['etag'] == f'"{report["snapshot_sha256"]}"'
    body = snapshot.json()
    assert body['assessment']['id'] == 1 and body['generated_at'] and isinstance(body['versions'], list)
    assert client.get(f'/api/reports/versions/{report_id}/snapshot', headers={**member, 'X-Salus-Tenant': '2'}).status_code == 404
    regenerated = post(client, '/api/reports/1', director)
    assert regenerated['id'] != report_id
    conn = app.db()
    conn.execute('UPDATE report_versions SET snapshot_json=? WHERE id=?', ('{"tampered":true}', regenerated['id']))
    conn.commit()
    conn.close()
    assert client.get(f"/api/reports/versions/{regenerated['id']}/snapshot", headers=director).status_code == 409

    finding = post(client, '/api/salintel/findings', director, {
        'assessment_id': 1, 'title': 'Role-aware finding', 'details': 'Protected source detail',
        'source': 'Confidential source', 'source_locator': 'protected://source/1',
    })
    assert client.post('/api/salintel/findings', headers=contributor, json={
        'assessment_id': 1, 'title': 'Forged internal finding', 'source': 'Member supplied',
    }).status_code == 403
    post(client, f"/api/salintel/findings/{finding['id']}/qualify", director, {
        'relevance': 'Relevant', 'credibility': 'High', 'validation_status': 'Qualified',
        'operational_significance': 'A member-facing protective action is warranted.',
    })
    operation = post(client, '/api/salops/requests', director, {
        'assessment_id': 1, 'title': 'Role-aware operation',
        'description': 'Internal operating detail', 'priority': 'Priority',
    })
    post(client, f"/api/salops/requests/{operation['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Protected Member authority basis', 'assigned_to': 'Operations Lead',
    })
    assert client.post(f"/api/salops/requests/{operation['id']}/complete", headers=contributor, json={
        'result_summary': 'Forged member completion',
    }).status_code == 403

    cop = client.get('/api/salcapa/common-operating-picture', headers=member).json()
    member_intel = next(x for x in cop['attention']['intelligence'] if x['id'] == finding['id'])
    member_ops = next(x for x in cop['attention']['operations'] if x['id'] == operation['id'])
    assert not {'details', 'source', 'source_locator', 'created_by'} & set(member_intel)
    assert not {'description', 'authorized_by', 'authorized_at'} & set(member_ops)
    listed_ops = next(x for x in client.get('/api/salops/requests', headers=member).json() if x['id'] == operation['id'])
    assert 'description' not in listed_ops and 'authorized_by' not in listed_ops

    member_history = client.get('/api/audit/assessments/1', headers=member)
    assert member_history.status_code == 200
    assert all(row['detail'] == 'Governed activity recorded.' for row in member_history.json()['audit'])
    assert all('snapshot_json' not in row for row in member_history.json()['versions'])

    conn = app.db()
    cur = conn.execute('INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)', ('Tenant Two', 'tenant-two', 'Active', app.now()))
    tenant_two = cur.lastrowid
    conn.commit()
    conn.close()
    tenant_two_director = {**director, 'X-Salus-User': 'Tenant Two Director', 'X-Salus-Tenant': str(tenant_two)}
    assessment_two = post(client, '/api/assessments', tenant_two_director, {'name': 'Tenant Two Assessment', 'organization': 'Tenant Two'})
    report_two = post(client, f"/api/reports/{assessment_two['id']}", tenant_two_director)
    conn = app.db()
    audit_two = conn.execute("SELECT * FROM audit_log WHERE entity_type='report_version' AND entity_id=? AND action='CREATE'", (report_two['id'],)).fetchone()
    conn.close()
    assert audit_two and audit_two['tenant_id'] == tenant_two

    backup = post(client, '/api/admin/backups', admin_requester)
    assert post(client, f"/api/admin/backups/{backup['id']}/verify", admin_requester)['ok']
    assert post(client, f"/api/admin/backups/{backup['id']}/dr-validate", admin_requester)['ok']
    assert client.post('/api/admin/restore-requests', headers=admin_requester, json={
        'backup_id': backup['id'], 'scope': 'Tenant 1 records', 'reason': 'Validation exercise',
        'status': 'Authorized', 'authorized_by': 'Forged',
    }).status_code == 422
    restore_request = post(client, '/api/admin/restore-requests', admin_requester, {
        'backup_id': backup['id'], 'scope': 'Tenant 1 authoritative records',
        'reason': 'Validated recovery exercise',
    })
    assert post(client, f"/api/admin/restore-requests/{restore_request['id']}/decision", admin_requester, {
        'decision': 'Authorized', 'reason': 'Self-approval attempt',
    }, 409)
    authorized = post(client, f"/api/admin/restore-requests/{restore_request['id']}/decision", admin_authority, {
        'decision': 'Authorized', 'reason': 'Independent scope and integrity review',
    })
    assert authorized['authorized_by'] == 'Recovery Authority'
    assert client.post(
        f"/api/admin/backups/{backup['id']}/restore?restore_request_id={restore_request['id']}",
        headers=admin_authority,
    ).status_code == 403
    assert client.get('/api/admin/backups', headers=member).status_code == 403

    print('SALCAPA_V21_REPORT_AUDIT_RECOVERY_ROLE_BOUNDARY_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
