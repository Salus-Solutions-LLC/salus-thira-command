#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v26.db'))
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
    staff = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Salus Coordinator', 'X-Salus-Tenant': '1'}
    analyst = {**staff, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'SalINTEL Analyst'}
    member = {**staff, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Authority'}
    contributor = {**staff, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member User'}
    auditor = {**staff, 'X-Salus-Role': 'Auditor', 'X-Salus-User': 'Independent Auditor'}

    finding = post(client, '/api/salintel/findings', analyst, {
        'assessment_id': 1, 'title': 'Qualified member condition',
        'details': 'Controlled source narrative that must not appear in the member COP.',
        'source': 'Protected source', 'source_locator': 'CONTROLLED-LOCATOR-001',
    })
    post(client, f"/api/salintel/findings/{finding['id']}/qualify", analyst, {
        'relevance': 'Relevant', 'credibility': 'High', 'validation_status': 'Qualified',
        'operational_significance': 'Leadership awareness and a priority decision are appropriate.',
    })

    cop = client.get('/api/salcapa/common-operating-picture', headers=member).json()
    assert set(cop) >= {'workspace', 'metrics', 'see', 'coordinate', 'act'}
    visible = next(x for x in cop['see']['intelligence'] if x['id'] == finding['id'])
    assert visible['title'] == 'Qualified member condition'
    assert not {'details', 'source', 'source_locator', 'qualified_by', 'tenant_id'} & set(visible)
    assert all(not {'description', 'assigned_to', 'resolution', 'affected_record_type'} & set(x) for x in cop['see']['alerts'])
    auditor_cop = client.get('/api/salcapa/common-operating-picture', headers=auditor).json()
    assert 'CONTROLLED-LOCATOR-001' not in json.dumps(auditor_cop)
    assert 'Controlled source narrative' not in json.dumps(auditor_cop)

    forged = client.post('/api/salcapa/coordination/threads', headers=contributor, json={
        'subject': 'Forged assignment', 'message': 'Attempted forged state', 'assessment_id': 1,
        'tenant_id': 2, 'status': 'Closed', 'assigned_contact': 'Forged Salus expert',
    })
    assert forged.status_code == 422
    thread = post(client, '/api/salcapa/coordination/threads', contributor, {
        'subject': 'Coordinate protective planning', 'message': 'Please coordinate the authorized next step.', 'assessment_id': 1,
    })
    assert thread['status'] == 'Open' and thread['assigned_contact'] == ''
    assert post(client, f"/api/salcapa/coordination/threads/{thread['id']}/assign", contributor, {
        'assigned_contact': 'Forged', 'member_contact_summary': 'Forged assignment',
    }, 403)
    post(client, f"/api/salcapa/coordination/threads/{thread['id']}/assign", staff, {
        'assigned_contact': 'Salus Coordinator', 'member_contact_summary': 'Salus coordination lead',
    })
    assert post(client, f"/api/salcapa/coordination/threads/{thread['id']}/messages", contributor, {
        'body': 'Attempt to create a hidden note', 'audience': 'Internal',
    }, 403)
    post(client, f"/api/salcapa/coordination/threads/{thread['id']}/messages", staff, {
        'body': 'Controlled internal note: personnel and tactics.', 'audience': 'Internal',
    })
    post(client, f"/api/salcapa/coordination/threads/{thread['id']}/messages", staff, {
        'body': 'Shared update approved for the Protected Member.', 'audience': 'Shared',
    })
    member_thread = next(x for x in client.get('/api/salcapa/common-operating-picture', headers=member).json()['coordinate']['threads'] if x['id'] == thread['id'])
    assert member_thread['assigned_contact_summary'] == 'Salus coordination lead'
    assert len(member_thread['messages']) == 2
    assert all(x.get('audience') is None for x in member_thread['messages'])
    assert 'personnel and tactics' not in json.dumps(member_thread)
    auditor_thread = next(x for x in client.get('/api/salcapa/common-operating-picture', headers=auditor).json()['coordinate']['threads'] if x['id'] == thread['id'])
    assert 'personnel and tactics' not in json.dumps(auditor_thread)

    forged_request = client.post('/api/salcapa/decision-requests', headers=staff, json={
        'source_type': 'intel_finding', 'source_id': finding['id'], 'action_type': 'Set Priority',
        'title': 'Set condition priority', 'member_summary': 'Select the member priority.',
        'allowed_choices': ['Forged'], 'status': 'Decision Recorded', 'tenant_id': 2,
    })
    assert forged_request.status_code == 422
    assert client.post('/api/salcapa/decision-requests', headers=member, json={
        'source_type': 'intel_finding', 'source_id': finding['id'], 'action_type': 'Set Priority',
        'title': 'Self-issued request', 'member_summary': 'Not permitted.',
    }).status_code == 403
    decision_request = post(client, '/api/salcapa/decision-requests', staff, {
        'source_type': 'intel_finding', 'source_id': finding['id'], 'action_type': 'Set Priority',
        'title': 'Set condition priority', 'member_summary': 'Select the priority for member coordination.',
        'due_at': '2026-12-01T17:00:00Z',
    })
    assert decision_request['allowed_choices'] == ['Routine', 'Priority', 'Urgent', 'Critical']
    assert decision_request['status'] == 'Awaiting Decision'
    assert post(client, f"/api/salcapa/decision-requests/{decision_request['id']}/decide", contributor, {
        'decision': 'Urgent', 'rationale': 'Forged contributor authority', 'authorized_amount': 0,
    }, 403)
    assert post(client, f"/api/salcapa/decision-requests/{decision_request['id']}/decide", member, {
        'decision': 'Forged choice', 'rationale': 'Attempted forged choice', 'authorized_amount': 0,
    }, 422)
    forged_decision = client.post(f"/api/salcapa/decision-requests/{decision_request['id']}/decide", headers=member, json={
        'decision': 'Urgent', 'rationale': 'Member priority requires prompt coordination.', 'authorized_amount': 0,
        'decided_by': 'Forged authority', 'status': 'Implemented', 'tenant_id': 2,
    })
    assert forged_decision.status_code == 422
    decided = post(client, f"/api/salcapa/decision-requests/{decision_request['id']}/decide", member, {
        'decision': 'Urgent', 'rationale': 'Member priority requires prompt coordination.',
        'conditions': '', 'authorized_amount': 0,
    })
    assert decided['status'] == 'Decision Recorded' and decided['decided_by'] == 'Protected Member Authority'
    assert post(client, f"/api/salcapa/decision-requests/{decision_request['id']}/decide", member, {
        'decision': 'Routine', 'rationale': 'Attempted rewrite', 'authorized_amount': 0,
    }, 409)
    second_request = post(client, '/api/salcapa/decision-requests', staff, {
        'source_type': 'intel_finding', 'source_id': finding['id'], 'action_type': 'Set Priority',
        'title': 'Scheduled priority review', 'member_summary': 'Review the priority after conditions change.',
    })
    assert second_request['id'] != decision_request['id']
    post(client, f"/api/salcapa/decision-requests/{second_request['id']}/withdraw", staff, {'reason': 'Conditions did not change.'})

    override = post(client, '/api/risk-overrides', member, {
        'assessment_id': 1, 'threat_id': 1, 'assigned_score': 72,
        'reason': 'Professional judgment recorded by authenticated authority.',
        'authority': 'Forged Authority Name', 'review_date': '2026-12-31',
    })
    assert override['authority'] == 'Protected Member Authority'

    conn = app.db()
    conn.execute("INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)",('Other tenant','other-tenant','Active',app.now()))
    conn.commit(); other_tid=conn.execute("SELECT id FROM tenants WHERE slug='other-tenant'").fetchone()['id']; conn.close()
    other = {**contributor, 'X-Salus-Tenant': str(other_tid), 'X-Salus-User': 'Other Tenant Member'}
    other_thread = post(client, '/api/salcapa/coordination/threads', other, {'subject': 'Other tenant', 'message': 'Isolated', 'assessment_id': None})
    assert client.post(f"/api/salcapa/coordination/threads/{other_thread['id']}/messages", headers=contributor, json={'body': 'Cross tenant', 'audience': 'Shared'}).status_code == 403

    post(client, f"/api/salcapa/coordination/threads/{thread['id']}/close", staff, {'reason': 'Coordination objective completed.'})
    assert client.post(f"/api/salcapa/coordination/threads/{thread['id']}/messages", headers=contributor, json={'body': 'Late message', 'audience': 'Shared'}).status_code == 409
    conn = app.db(); records = collect_tenant_records(conn, 1)
    events = [r for r in records['cop_events'] if r['record_type'] == 'coordination_thread' and r['record_id'] == thread['id']]
    audit_tenants = {r['tenant_id'] for r in conn.execute("SELECT tenant_id FROM audit_log WHERE tenant_id=1 AND entity_type IN ('coordination_thread','coordination_message','decision_request')")}
    boundary_events = conn.execute("SELECT COUNT(*) c FROM security_events WHERE event_type='COP_TENANT_BOUNDARY_VIOLATION'").fetchone()['c']; conn.close()
    assert [r['version_no'] for r in events] == list(range(1, len(events) + 1))
    validation_errors=validate_records(records, 1)
    assert not validation_errors, validation_errors
    assert audit_tenants == {1}, audit_tenants
    assert boundary_events == 1, boundary_events
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = conn.execute('SELECT COUNT(*) c FROM cop_coordination_threads WHERE tenant_id=1').fetchone()['c']
    restored_decisions = conn.execute('SELECT COUNT(*) c FROM cop_decision_requests WHERE tenant_id=1').fetchone()['c']; conn.close()
    assert restored == 1 and restored_decisions == 2
    print('SALCAPA_V26_SEE_COORDINATE_ACT_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
