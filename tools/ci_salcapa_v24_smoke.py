#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v24.db'))
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
    creator = {'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'Statement Creator', 'X-Salus-Tenant': '1'}
    reviewer = {**creator, 'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Statement Reviewer'}
    approver = {**creator, 'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'Statement Approver'}
    expense_author = {**creator, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'Expense Author'}
    member = {**creator, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Executive'}
    contributor = {**creator, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member Requester'}

    request_record = post(client, '/api/salops/requests', contributor, {
        'assessment_id': 1, 'title': 'Invoice-ready engagement',
        'description': 'Exercise immutable member-safe statement governance.', 'priority': 'Priority',
    })
    post(client, f"/api/salops/requests/{request_record['id']}/decision", member, {
        'decision': 'Authorized', 'reason': 'Member authorized operational support', 'assigned_to': 'Operations Lead',
    })
    engagement = post(client, f"/api/salops/requests/{request_record['id']}/engagement", creator, {
        'service_type': 'Protective Services', 'objective': 'Complete governed protective support',
        'location': 'Controlled location', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'Operations Lead',
        'communications_plan': 'Controlled communications plan', 'member_status_summary': 'Planning is underway.',
    })
    eid = engagement['id']
    estimate = post(client, f'/api/salops/engagements/{eid}/estimates', expense_author, {
        'currency': 'USD', 'member_summary': 'Approved protective services estimate.',
        'internal_basis': 'Controlled staffing model and rate card.',
        'lines': [{'category': 'Labor', 'description': 'Protective coverage', 'quantity': '10', 'unit': 'hour', 'unit_rate': '125.00'}],
    })
    post(client, f"/api/salops/estimates/{estimate['id']}/transition", expense_author, {
        'status': 'Submitted', 'reason': 'Estimate submitted after internal review',
    })
    post(client, f"/api/salops/estimates/{estimate['id']}/transition", member, {
        'status': 'Approved', 'reason': 'Member approved estimate',
    })
    post(client, f'/api/salops/engagements/{eid}/transition', creator, {
        'status': 'Mobilizing', 'reason': 'Resources assigned', 'member_status_summary': 'Resources are mobilizing.',
    })
    expense = post(client, f'/api/salops/engagements/{eid}/expenses', expense_author, {
        'category': 'Labor', 'description': 'Controlled personnel and shift detail',
        'member_description': 'Approved protective services', 'vendor': 'Controlled Vendor',
        'incurred_on': '2026-09-10', 'amount': '1125.50', 'currency': 'USD', 'reimbursable': True,
    })
    post(client, f"/api/salops/expenses/{expense['id']}/transition", expense_author, {
        'status': 'Submitted', 'reason': 'Actual service record reconciled',
    })
    post(client, f"/api/salops/expenses/{expense['id']}/transition", creator, {
        'status': 'Approved', 'reason': 'Independent operational expense review completed',
    })
    post(client, f'/api/salops/engagements/{eid}/transition', creator, {
        'status': 'Active', 'reason': 'Operational readiness confirmed', 'member_status_summary': 'Protective operations are active.',
    })
    report = post(client, f'/api/salops/engagements/{eid}/field-reports', expense_author, {
        'report_type': 'Completion Update', 'occurred_at': '2026-09-11T11:00:00Z',
        'member_summary': 'Approved protective services completed safely.',
        'internal_details': 'Controlled location, personnel, and timing details.',
    })
    post(client, f"/api/salops/field-reports/{report['id']}/release", reviewer, {
        'reason': 'Member summary reviewed for controlled information',
    })
    post(client, f'/api/salops/engagements/{eid}/transition', creator, {
        'status': 'Demobilizing', 'reason': 'Services completed', 'member_status_summary': 'Operations are demobilizing normally.',
    })
    unresolved_expense = post(client, f'/api/salops/engagements/{eid}/expenses', expense_author, {
        'category': 'Travel', 'description': 'Cancelled draft travel charge',
        'member_description': 'Travel charge under review', 'incurred_on': '2026-09-11',
        'amount': '25.00', 'currency': 'USD', 'reimbursable': True,
    })
    assert client.post(f'/api/salops/engagements/{eid}/invoice-statements', headers=creator, json={
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11', 'service_summary': 'Premature statement',
    }).status_code == 409
    post(client, f'/api/salops/engagements/{eid}/transition', creator, {
        'status': 'Closed', 'reason': 'All operational objectives and records reconciled', 'member_status_summary': 'The engagement is complete.',
    })
    assert client.post(f'/api/salops/engagements/{eid}/invoice-statements', headers=creator, json={
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11', 'service_summary': 'Blocked unresolved expense',
    }).status_code == 409
    post(client, f"/api/salops/expenses/{unresolved_expense['id']}/transition", expense_author, {
        'status': 'Submitted', 'reason': 'Submitted for final disposition',
    })
    post(client, f"/api/salops/expenses/{unresolved_expense['id']}/transition", creator, {
        'status': 'Rejected', 'reason': 'Travel was cancelled and is not billable',
    })

    forged = client.post(f'/api/salops/engagements/{eid}/invoice-statements', headers=creator, json={
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11',
        'service_summary': 'Protective services completed.', 'billable_total_cents': 1,
        'status': 'Released', 'statement_number': 'FORGED', 'tenant_id': 2, 'snapshot_sha256': 'forged',
    })
    assert forged.status_code == 422
    assert client.post(f'/api/salops/engagements/{eid}/invoice-statements', headers=contributor, json={
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11', 'service_summary': 'Forged',
    }).status_code == 403
    statement = post(client, f'/api/salops/engagements/{eid}/invoice-statements', creator, {
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11',
        'service_summary': 'Protective services completed during the approved operating period.',
    })
    sid = statement['id']
    assert statement['status'] == 'Draft' and statement['billable_total'] == '1125.50'
    assert statement['estimate_total'] == '1250.00' and statement['variance'] == '124.50'
    assert statement['statement_number'].startswith('SIR-0001-')
    assert client.get(f'/api/salops/engagements/{eid}/invoice-statements', headers=contributor).json() == []
    assert client.get(f'/api/salops/invoice-statements/{sid}/snapshot', headers=member).status_code == 404
    assert client.get(f'/api/versions/ops_invoice_statements/{sid}', headers=member).status_code == 403
    assert post(client, f'/api/salops/invoice-statements/{sid}/transition', creator, {
        'status': 'Reviewed', 'reason': 'Attempted self review',
    }, 409)
    post(client, f'/api/salops/invoice-statements/{sid}/transition', reviewer, {
        'status': 'Reviewed', 'reason': 'Scope, approvals, and actuals reconciled',
    })
    assert post(client, f'/api/salops/invoice-statements/{sid}/transition', reviewer, {
        'status': 'Approved', 'reason': 'Attempted reviewer approval',
    }, 409)
    post(client, f'/api/salops/invoice-statements/{sid}/transition', approver, {
        'status': 'Approved', 'reason': 'Independent authority confirmed invoice readiness',
    })
    assert post(client, f'/api/salops/invoice-statements/{sid}/transition', reviewer, {
        'status': 'Released', 'reason': 'Unauthorized release attempt',
    }, 409)
    released = post(client, f'/api/salops/invoice-statements/{sid}/transition', approver, {
        'status': 'Released', 'reason': 'Approved member-safe statement released',
    })
    assert released['status'] == 'Released' and released['billable_total'] == '1125.50'
    assert released['created_by'] == 'Statement Creator' and released['approved_by'] == 'Statement Approver'

    member_rows = client.get(f'/api/salops/engagements/{eid}/invoice-statements', headers=contributor).json()
    assert len(member_rows) == 1 and member_rows[0]['statement_number'] == statement['statement_number']
    assert not {'created_by', 'reviewed_by', 'approved_by', 'released_by', 'snapshot_json'} & set(member_rows[0])
    snapshot_response = client.get(f'/api/salops/invoice-statements/{sid}/snapshot', headers=member)
    assert snapshot_response.status_code == 200 and snapshot_response.headers['etag'] == f'"{statement["snapshot_sha256"]}"'
    snapshot = snapshot_response.json(); serialized = json.dumps(snapshot)
    assert snapshot['statement_type'] == 'Invoice Ready - Not Issued'
    assert snapshot['totals']['billable'] == '1125.50' and snapshot['lines'][0]['description'] == 'Approved protective services'
    assert not any(value in serialized for value in ('Controlled Vendor', 'Controlled personnel', 'Expense Author', 'evidence_id', 'vendor'))
    assert client.post(f'/api/salops/engagements/{eid}/invoice-statements', headers=creator, json={
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11', 'service_summary': 'Duplicate',
    }).status_code == 409

    conn = app.db(); records = collect_tenant_records(conn, 1)
    version_count = conn.execute("SELECT COUNT(*) c FROM entity_versions WHERE entity_type='ops_invoice_statements'").fetchone()['c']
    audit_tenants = {r['tenant_id'] for r in conn.execute("SELECT tenant_id FROM audit_log WHERE entity_type='ops_invoice_statement'")}
    conn.close()
    assert len(records['ops_invoice_statements']) == 1 and validate_records(records, 1) == []
    assert version_count == 4 and audit_tenants == {1}
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = conn.execute('SELECT COUNT(*) c FROM ops_invoice_statements WHERE tenant_id=1').fetchone()['c']; conn.close()
    assert restored == 1

    conn = app.db(); conn.execute("UPDATE ops_invoice_statements SET snapshot_json='{}' WHERE id=?", (sid,)); conn.commit(); conn.close()
    assert client.get(f'/api/salops/invoice-statements/{sid}/snapshot', headers=member).status_code == 409
    conn = app.db(); integrity_events = conn.execute("SELECT COUNT(*) c FROM security_events WHERE event_type='INVOICE_READY_INTEGRITY_FAILURE'").fetchone()['c']; conn.close()
    assert integrity_events == 1

    print('SALCAPA_V24_INVOICE_READY_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
