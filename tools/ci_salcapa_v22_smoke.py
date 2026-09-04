#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v22.db'))
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
    director = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Operations Director', 'X-Salus-Tenant': '1'}
    program_owner = {**director, 'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'Operations Lead'}
    member = {**director, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Executive'}
    contributor = {**director, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member Requester'}

    request_record = post(client, '/api/salops/requests', contributor, {
        'assessment_id': 1, 'title': 'Executive protection movement',
        'description': 'Protected Member requests coordinated protective movement.', 'priority': 'Priority',
    })
    authorized = post(client, f"/api/salops/requests/{request_record['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Member authority confirms service requirement', 'assigned_to': 'Operations Lead',
    })
    assert authorized['status'] == 'Authorized'

    forged = client.post(f"/api/salops/requests/{request_record['id']}/engagement", headers=director, json={
        'service_type': 'Executive Protection', 'objective': 'Protect movement', 'location': 'Member operating area',
        'planned_start': '2026-09-10T12:00:00Z', 'planned_end': '2026-09-10T20:00:00Z',
        'operational_lead': 'Operations Lead', 'communications_plan': 'Controlled communications channel',
        'member_status_summary': 'Planning is underway.', 'status': 'Active', 'tenant_id': 2,
    })
    assert forged.status_code == 422
    assert client.post(f"/api/salops/requests/{request_record['id']}/engagement", headers=contributor, json={
        'service_type': 'Executive Protection', 'objective': 'Protect movement', 'planned_start': '2026-09-10',
        'planned_end': '2026-09-11', 'operational_lead': 'Forged Lead', 'communications_plan': 'Forged',
        'member_status_summary': 'Forged',
    }).status_code == 403

    engagement = post(client, f"/api/salops/requests/{request_record['id']}/engagement", director, {
        'service_type': 'Executive Protection', 'objective': 'Provide coordinated protective movement',
        'location': 'Member operating area', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-10T20:00:00Z', 'operational_lead': 'Operations Lead',
        'communications_plan': 'Use the controlled operations channel and escalation roster.',
        'member_status_summary': 'Planning and coordination are underway.',
    })
    engagement_id = engagement['id']
    assert engagement['status'] == 'Planning' and engagement['tenant_id'] == 1
    assert engagement['authorized_by'] == 'Protected Member Executive'
    assert client.post(f"/api/salops/requests/{request_record['id']}/engagement", headers=director, json={
        'service_type': 'Duplicate', 'objective': 'Duplicate', 'planned_start': '2026-09-10', 'planned_end': '2026-09-11',
        'operational_lead': 'Lead', 'communications_plan': 'Plan', 'member_status_summary': 'Summary',
    }).status_code == 409
    assert client.put(f'/api/ops_engagements/{engagement_id}', headers=director, json={'status': 'Closed'}).status_code == 404

    member_engagement = next(x for x in client.get('/api/salops/engagements', headers=member).json() if x['id'] == engagement_id)
    assert not {'objective', 'location', 'operational_lead', 'communications_plan', 'authorized_by', 'created_by'} & set(member_engagement)
    assert client.get(f'/api/salops/engagements/{engagement_id}/tasks', headers=member).status_code == 403

    assert client.post(f'/api/salops/engagements/{engagement_id}/tasks', headers=director, json={
        'title': 'Advance route review', 'instructions': 'Review controlled route information',
        'assigned_to': 'Agent One', 'priority': 'Priority', 'status': 'Completed',
    }).status_code == 422
    task = post(client, f'/api/salops/engagements/{engagement_id}/tasks', director, {
        'title': 'Advance route review', 'instructions': 'Review controlled route information and contingencies.',
        'assigned_to': 'Agent One', 'priority': 'Priority',
    })
    assert task['status'] == 'Assigned' and task['created_by'] == 'Operations Director'
    assert post(client, f"/api/salops/tasks/{task['id']}/transition", director, {
        'status': 'Completed', 'reason': 'Attempt to skip start', 'result_summary': 'Forged direct completion',
    }, 409)
    assert client.post(f"/api/salops/tasks/{task['id']}/transition", headers=contributor, json={
        'status': 'In Progress', 'reason': 'Member attempted internal task action',
    }).status_code == 403
    post(client, f"/api/salops/tasks/{task['id']}/transition", program_owner, {
        'status': 'In Progress', 'reason': 'Assigned agent began advance work',
    })
    completed = post(client, f"/api/salops/tasks/{task['id']}/transition", program_owner, {
        'status': 'Completed', 'reason': 'Advance work reviewed', 'result_summary': 'Primary and contingency routes validated.',
    })
    assert completed['completed_by'] == 'Operations Lead'

    post(client, f'/api/salops/engagements/{engagement_id}/transition', program_owner, {
        'status': 'Mobilizing', 'reason': 'Resources assigned and pre-operation checks started',
        'member_status_summary': 'Resources are mobilizing.',
    })
    active = post(client, f'/api/salops/engagements/{engagement_id}/transition', program_owner, {
        'status': 'Active', 'reason': 'Operational lead confirmed readiness',
        'member_status_summary': 'Protective operations are active.',
    })
    assert active['engagement']['status'] == 'Active'
    assert client.get('/api/salops/requests', headers=director).json()[0]['status'] == 'In Progress'

    assert client.post(f'/api/salops/engagements/{engagement_id}/field-reports', headers=director, json={
        'report_type': 'Situation Update', 'occurred_at': '2026-09-10T14:00:00Z',
        'member_summary': 'Movement completed safely.', 'internal_details': 'Controlled operational details.',
        'status': 'Released',
    }).status_code == 422
    assert client.post(f'/api/salops/engagements/{engagement_id}/field-reports', headers=contributor, json={
        'report_type': 'Situation Update', 'occurred_at': '2026-09-10T14:00:00Z',
        'member_summary': 'Forged', 'internal_details': 'Forged',
    }).status_code == 403
    report = post(client, f'/api/salops/engagements/{engagement_id}/field-reports', director, {
        'task_id': task['id'], 'report_type': 'Situation Update', 'occurred_at': '2026-09-10T14:00:00Z',
        'member_summary': 'Movement completed safely and operations remain on schedule.',
        'internal_details': 'Controlled route, timing, personnel, and communications observations.',
    })
    assert report['status'] == 'Draft'
    assert client.get(f'/api/salops/engagements/{engagement_id}/field-reports', headers=member).json() == []
    released = post(client, f"/api/salops/field-reports/{report['id']}/release", program_owner, {
        'reason': 'Operational lead verified the summary contains no controlled detail',
    })
    assert released['status'] == 'Released' and released['released_by'] == 'Operations Lead'
    member_report = client.get(f'/api/salops/engagements/{engagement_id}/field-reports', headers=member).json()[0]
    assert member_report['member_summary'].startswith('Movement completed safely')
    assert not {'internal_details', 'submitted_by', 'task_id', 'released_by', 'release_reason'} & set(member_report)

    blocking_task = post(client, f'/api/salops/engagements/{engagement_id}/tasks', director, {
        'title': 'Demobilization inventory', 'instructions': 'Account for controlled equipment.',
        'assigned_to': 'Agent Two', 'priority': 'Routine',
    })
    post(client, f'/api/salops/engagements/{engagement_id}/transition', program_owner, {
        'status': 'Demobilizing', 'reason': 'Protective movement completed',
        'member_status_summary': 'Operations are demobilizing normally.',
    })
    assert post(client, f'/api/salops/engagements/{engagement_id}/transition', program_owner, {
        'status': 'Closed', 'reason': 'Attempted closure with open task',
        'member_status_summary': 'Attempted closure.',
    }, 409)
    post(client, f"/api/salops/tasks/{blocking_task['id']}/transition", program_owner, {
        'status': 'Cancelled', 'reason': 'Inventory transferred to standing logistics process',
    })
    closed = post(client, f'/api/salops/engagements/{engagement_id}/transition', program_owner, {
        'status': 'Closed', 'reason': 'All operational objectives completed and records reconciled',
        'member_status_summary': 'The engagement is complete.',
    })
    assert closed['engagement']['status'] == 'Closed' and closed['reassessment_trigger_id']
    assert client.post(f'/api/salops/engagements/{engagement_id}/transition', headers=program_owner, json={
        'status': 'Closed', 'reason': 'Duplicate closure', 'member_status_summary': 'Duplicate',
    }).status_code == 409

    conn = app.db()
    ops_request = conn.execute('SELECT * FROM ops_requests WHERE id=?', (request_record['id'],)).fetchone()
    trigger_count = conn.execute("SELECT COUNT(*) c FROM reassessment_triggers WHERE affected_record_type='ops_engagement' AND affected_record_id=?", (engagement_id,)).fetchone()['c']
    audit_tenant = conn.execute("SELECT tenant_id FROM audit_log WHERE entity_type='ops_engagement' AND entity_id=? ORDER BY id LIMIT 1", (engagement_id,)).fetchone()['tenant_id']
    records = collect_tenant_records(conn, 1)
    conn.close()
    assert ops_request['status'] == 'Completed' and trigger_count == 1 and audit_tenant == 1
    assert len(records['ops_engagements']) == 1 and len(records['ops_tasks']) == 2 and len(records['ops_field_reports']) == 1
    assert validate_records(records, 1) == []
    conn = app.db()
    replace_tenant_records(conn, 1, records)
    conn.commit()
    restored = (
        conn.execute('SELECT COUNT(*) c FROM ops_engagements WHERE tenant_id=1').fetchone()['c'],
        conn.execute('SELECT COUNT(*) c FROM ops_tasks WHERE tenant_id=1').fetchone()['c'],
        conn.execute('SELECT COUNT(*) c FROM ops_field_reports WHERE tenant_id=1').fetchone()['c'],
    )
    conn.close()
    assert restored == (1, 2, 1)

    print('SALCAPA_V22_OPERATIONAL_ENGAGEMENT_TASKING_FIELD_REPORT_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
