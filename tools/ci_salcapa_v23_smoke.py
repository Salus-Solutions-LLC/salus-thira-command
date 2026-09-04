#!/usr/bin/env python3
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v23.db'))
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
    director = {'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Estimate Author', 'X-Salus-Tenant': '1'}
    program_owner = {**director, 'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'Expense Approver'}
    member = {**director, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Executive'}
    contributor = {**director, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member Requester'}

    request_record = post(client, '/api/salops/requests', contributor, {
        'assessment_id': 1, 'title': 'Governed protection engagement',
        'description': 'Operational support with estimate and actual governance.', 'priority': 'Priority',
    })
    post(client, f"/api/salops/requests/{request_record['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Member authorized operational support', 'assigned_to': 'Operations Lead',
    })
    engagement = post(client, f"/api/salops/requests/{request_record['id']}/engagement", director, {
        'service_type': 'Executive Protection', 'objective': 'Govern approved operational support',
        'location': 'Controlled', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'Operations Lead',
        'communications_plan': 'Controlled communications plan', 'member_status_summary': 'Planning is underway.',
    })
    eid = engagement['id']

    forged = client.post(f'/api/salops/engagements/{eid}/estimates', headers=director, json={
        'currency': 'USD', 'member_summary': 'Protection services', 'internal_basis': 'Reviewed rate card',
        'total_cents': 1, 'status': 'Approved', 'tenant_id': 2,
        'lines': [{'category': 'Labor', 'description': 'Protection coverage', 'quantity': '10', 'unit': 'hour', 'unit_rate': '125.55'}],
    })
    assert forged.status_code == 422
    assert client.post(f'/api/salops/engagements/{eid}/estimates', headers=contributor, json={
        'currency': 'USD', 'member_summary': 'Forged', 'internal_basis': 'Forged',
        'lines': [{'category': 'Labor', 'description': 'Forged', 'quantity': '1', 'unit': 'hour', 'unit_rate': '1'}],
    }).status_code == 403
    estimate = post(client, f'/api/salops/engagements/{eid}/estimates', director, {
        'currency': 'USD', 'member_summary': 'Protective services and approved travel allowance.',
        'internal_basis': 'Controlled staffing plan and reviewed rate card.',
        'lines': [
            {'category': 'Labor', 'description': 'Protection coverage', 'quantity': '10', 'unit': 'hour', 'unit_rate': '125.55'},
            {'category': 'Travel', 'description': 'Approved ground travel allowance', 'quantity': '2', 'unit': 'trip', 'unit_rate': '45.25'},
        ],
    })
    assert estimate['status'] == 'Draft' and estimate['total_amount'] == '1346.00'
    assert estimate['lines'][0]['line_total'] == '1255.50'
    submitted = post(client, f"/api/salops/estimates/{estimate['id']}/transition", director, {
        'status': 'Submitted', 'reason': 'Estimate reviewed and submitted to member authority',
    })
    assert submitted['submitted_by'] == 'Estimate Author'
    assert post(client, f"/api/salops/estimates/{estimate['id']}/transition", director, {
        'status': 'Approved', 'reason': 'Attempted self approval',
    }, 409)
    approved = post(client, f"/api/salops/estimates/{estimate['id']}/transition", member, {
        'status': 'Approved', 'reason': 'Member approved scope and estimate',
    })
    assert approved['status'] == 'Approved' and approved['total_amount'] == '1346.00'
    assert not {'internal_basis', 'created_by', 'submitted_by', 'decided_by', 'lines', 'total_cents'} & set(approved)

    post(client, f'/api/salops/engagements/{eid}/transition', program_owner, {
        'status': 'Mobilizing', 'reason': 'Resources assigned', 'member_status_summary': 'Resources are mobilizing.',
    })
    expense_forgery = client.post(f'/api/salops/engagements/{eid}/expenses', headers=director, json={
        'category': 'Travel', 'description': 'Ground travel', 'member_description': 'Approved travel',
        'incurred_on': '2026-09-10', 'amount': '80.25', 'currency': 'USD', 'status': 'Approved', 'amount_cents': 1,
    })
    assert expense_forgery.status_code == 422
    expense = post(client, f'/api/salops/engagements/{eid}/expenses', director, {
        'category': 'Travel', 'description': 'Controlled vendor ground movement',
        'member_description': 'Approved operational ground travel', 'vendor': 'Controlled Vendor',
        'incurred_on': '2026-09-10', 'amount': '80.25', 'currency': 'USD', 'reimbursable': True,
    })
    assert expense['status'] == 'Draft' and expense['amount'] == '80.25'
    post(client, f"/api/salops/expenses/{expense['id']}/transition", director, {
        'status': 'Submitted', 'reason': 'Receipt and service basis reviewed',
    })
    assert post(client, f"/api/salops/expenses/{expense['id']}/transition", director, {
        'status': 'Approved', 'reason': 'Attempted self approval',
    }, 409)
    approved_expense = post(client, f"/api/salops/expenses/{expense['id']}/transition", program_owner, {
        'status': 'Approved', 'reason': 'Independent operational review completed',
    })
    assert approved_expense['decided_by'] == 'Expense Approver'

    internal = client.get(f'/api/salops/engagements/{eid}/financials', headers=director).json()
    assert internal['approved_estimate_total'] == '1346.00'
    assert internal['approved_actual_total'] == '80.25'
    assert internal['remaining_estimate'] == '1265.75'
    assert internal['expenses'][0]['vendor'] == 'Controlled Vendor'
    member_view = client.get(f'/api/salops/engagements/{eid}/financials', headers=contributor).json()
    assert member_view['approved_actual_count'] == 1 and 'expenses' not in member_view
    assert not {'internal_basis', 'created_by', 'lines'} & set(member_view['estimates'][0])

    conn = app.db()
    records = collect_tenant_records(conn, 1)
    audit_tenants = {r['tenant_id'] for r in conn.execute("SELECT tenant_id FROM audit_log WHERE entity_type IN ('ops_estimate','ops_expense')")}
    version_count = conn.execute("SELECT COUNT(*) c FROM entity_versions WHERE entity_type IN ('ops_estimates','ops_expenses')").fetchone()['c']
    conn.close()
    assert len(records['ops_estimates']) == 1 and len(records['ops_estimate_lines']) == 2 and len(records['ops_expenses']) == 1
    assert validate_records(records, 1) == [] and audit_tenants == {1} and version_count >= 6
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = tuple(conn.execute(f'SELECT COUNT(*) c FROM {table} WHERE tenant_id=1').fetchone()['c'] for table in ('ops_estimates','ops_estimate_lines','ops_expenses'))
    conn.close(); assert restored == (1, 2, 1)

    print('SALCAPA_V23_OPERATIONAL_FINANCIAL_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
