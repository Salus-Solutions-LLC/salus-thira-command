#!/usr/bin/env python3
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-acceptance.db'))
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
    member_user = {'X-Salus-Tenant': '1', 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member User'}
    member_authority = {**member_user, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Authority'}
    intel = {**member_user, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'SalINTEL Analyst'}
    thira = {**member_user, 'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'SalTHIRA Assessor'}
    ops = {**member_user, 'X-Salus-Role': 'Program Owner', 'X-Salus-User': 'SalOPS Coordinator'}
    reviewer = {**member_user, 'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Independent Reviewer'}
    expert = {**member_user, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'Acceptance Assigned Expert'}
    admin = {**member_user, 'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'System Administrator'}
    recovery = {**admin, 'X-Salus-User': 'Recovery Authority'}
    auditor = {**member_user, 'X-Salus-Role': 'Auditor', 'X-Salus-User': 'Independent Auditor'}
    assessment_id = 1

    observation = post(client, '/api/observations', member_user, {
        'reporter_choice': 'Identified', 'reporter_name': 'Protected Member User',
        'reporter_contact': 'member@example.test', 'title': 'Continuity warning',
        'narrative': 'CONTROLLED SOURCE NARRATIVE requiring qualification.',
        'location': 'CONTROLLED MEMBER LOCATION', 'observed_at': '2026-09-04T08:00:00Z',
        'context': 'CONTROLLED REPORTER CONTEXT', 'reported_urgency': 'Priority',
        'emergency_acknowledged': True,
    })
    post(client, f"/api/observations/{observation['id']}/acknowledge", intel, {'reason': 'Receipt recorded; source remains unverified.'})
    post(client, f"/api/observations/{observation['id']}/triage", thira, {
        'category': 'Operational', 'priority': 'Priority', 'assigned_to': 'SalINTEL Analyst',
        'notes': 'Professional qualification is required.',
    })
    routed = post(client, f"/api/observations/{observation['id']}/route", intel, {
        'target': 'SalINTEL', 'assessment_id': assessment_id,
        'member_summary': 'Continuity condition routed for qualification.',
        'reason': 'Triage supports governed SalINTEL review.',
    })
    finding_id = routed['routed_record_id']
    post(client, f'/api/salintel/findings/{finding_id}/qualify', intel, {
        'relevance': 'Relevant', 'credibility': 'High', 'validation_status': 'Qualified',
        'operational_significance': 'Continuity capability should be reassessed.',
    })
    handoff = post(client, f'/api/salintel/findings/{finding_id}/send-to-salthira', intel)
    assert handoff['reassessment_trigger_id']

    threat = post(client, '/api/threats', thira, {
        'assessment_id': assessment_id, 'name': 'Continuity disruption', 'category': 'Operational',
        'description': 'Qualified condition requiring scenario analysis.', 'likelihood': 4,
        'vulnerability': 4, 'consequence': 4, 'basis': 'Qualified SalINTEL handoff.',
    })
    scenario = post(client, '/api/scenarios', thira, {
        'assessment_id': assessment_id, 'threat_id': threat['id'], 'title': 'Extended disruption',
        'narrative': 'Sustained disruption affects priority operations.',
    })
    capability = post(client, '/api/capabilities', thira, {
        'assessment_id': assessment_id, 'scenario_id': scenario['id'], 'name': 'Continuity recovery',
        'required_outcome': 'Restore priority services.', 'required_standard': 95, 'current_performance': 55,
    })
    gap = post(client, '/api/gaps', thira, {
        'assessment_id': assessment_id, 'capability_id': capability['id'],
        'description': 'Validated performance remains below the required target.', 'severity': 'High',
    })
    improvement = post(client, '/api/improvements', thira, {
        'assessment_id': assessment_id, 'gap_id': gap['id'], 'title': 'Add independent recovery path',
        'description': 'Implement and exercise a separately governed recovery capability.',
        'initial_cost': 5000, 'owner': 'Continuity Program Owner',
    })
    decision_payload = {
        'assessment_id': assessment_id, 'improvement_id': improvement['id'], 'decision_type': 'Approve',
        'authority': 'CLIENT CANNOT SET AUTHORITY', 'rationale': 'The improvement addresses a priority gap.',
        'funding_authorized': 5000, 'implementation_owner': 'Continuity Program Owner',
        'target_completion': (date.today() + timedelta(days=90)).isoformat(),
    }
    post(client, '/api/decisions', thira, decision_payload, 403)
    decision = post(client, '/api/decisions', member_authority, decision_payload)
    assert decision['authority'] == 'Protected Member Authority'
    ops_request = post(client, f"/api/salthira/improvements/{improvement['id']}/send-to-salops", thira)
    assert ops_request['status'] == 'Authorized' and ops_request['authorized_by'] == 'Protected Member Authority'

    manual_request = post(client, '/api/salops/requests', member_user, {
        'assessment_id': assessment_id, 'title': 'Authority boundary check', 'priority': 'Routine',
    })
    post(client, f"/api/salops/requests/{manual_request['id']}/decision", admin, {
        'decision': 'Authorized', 'reason': 'Administrative role cannot substitute for member authority.'
    }, 403)
    post(client, f"/api/salops/requests/{manual_request['id']}/decision", member_authority, {
        'decision': 'Rejected', 'reason': 'The duplicate request is unnecessary.'
    })

    engagement = post(client, f"/api/salops/requests/{ops_request['id']}/engagement", ops, {
        'service_type': 'Recovery support', 'objective': 'Deliver the authorized recovery improvement.',
        'location': 'CONTROLLED OPERATING LOCATION', 'planned_start': '2026-09-10T12:00:00Z',
        'planned_end': '2026-09-11T12:00:00Z', 'operational_lead': 'CONTROLLED OPERATIONS LEAD',
        'communications_plan': 'CONTROLLED COMMUNICATIONS PLAN', 'member_status_summary': 'Planning is underway.',
    })
    engagement_id = engagement['id']
    estimate = post(client, f'/api/salops/engagements/{engagement_id}/estimates', intel, {
        'currency': 'USD', 'member_summary': 'Authorized recovery support estimate.',
        'internal_basis': 'CONTROLLED PRICING BASIS',
        'lines': [{'category': 'Labor', 'description': 'Recovery support', 'quantity': '8', 'unit': 'hour', 'unit_rate': '125.00'}],
    })
    post(client, f"/api/salops/estimates/{estimate['id']}/transition", intel, {'status': 'Submitted', 'reason': 'Estimate submitted.'})
    post(client, f"/api/salops/estimates/{estimate['id']}/transition", member_authority, {'status': 'Approved', 'reason': 'Member authorized the estimate.'})

    profile = post(client, '/api/salops/experts', ops, {
        'expert_actor': 'Acceptance Assigned Expert', 'member_display_name': 'Jordan Lee',
        'member_role_title': 'Continuity Advisor', 'member_biography': 'Qualified advisor for the authorized engagement.',
        'member_contact_summary': 'Coordinate through the approved Salus channel.',
        'internal_biography': 'CONTROLLED PERSONNEL HISTORY', 'disciplines': 'Continuity',
        'jurisdictions': 'United States', 'regions': 'Midwest',
    })
    post(client, f"/api/salops/experts/{profile['id']}/transition", reviewer, {'action': 'Activate', 'reason': 'Profile independently approved.'})
    credential = post(client, f"/api/salops/experts/{profile['id']}/credentials", ops, {
        'credential_type': 'Continuity qualification', 'issuer': 'Qualified Authority',
        'jurisdiction': 'United States', 'effective_on': '2026-01-01', 'expires_on': '2099-12-31',
    })
    post(client, f"/api/salops/credentials/{credential['id']}/transition", admin, {'action': 'Verify', 'reason': 'Credential independently verified.'})
    post(client, f"/api/salops/experts/{profile['id']}/availability", expert, {
        'available_from': '2026-09-09T00:00:00Z', 'available_until': '2026-09-12T00:00:00Z', 'region': 'Midwest',
    })
    conflict = post(client, f'/api/salops/engagements/{engagement_id}/conflicts', expert, {
        'profile_id': profile['id'], 'disclosure': 'No known conflict; independent review requested.',
    })
    post(client, f"/api/salops/conflicts/{conflict['id']}/review", reviewer, {'decision': 'Cleared', 'reason': 'Disclosure independently cleared.'})
    assignment = post(client, f'/api/salops/engagements/{engagement_id}/experts', ops, {
        'profile_id': profile['id'], 'conflict_id': conflict['id'], 'assignment_role': 'Continuity Advisor', 'member_visible': True,
    })
    post(client, f"/api/salops/expert-assignments/{assignment['id']}/transition", expert, {'action': 'Accept', 'reason': 'Assignment accepted.'})
    readiness = post(client, f'/api/salops/engagements/{engagement_id}/readiness', ops, {
        'label': 'Delivery readiness', 'member_summary': 'Qualified support is ready.',
        'internal_requirement': 'CONTROLLED READINESS DETAIL', 'member_visible': True,
    })
    post(client, f'/api/salops/engagements/{engagement_id}/transition', ops, {
        'status': 'Mobilizing', 'reason': 'Qualified assignment accepted.', 'member_status_summary': 'Resources are mobilizing.',
    })
    post(client, f"/api/salops/readiness/{readiness['id']}/transition", reviewer, {'status': 'Complete', 'reason': 'Readiness independently confirmed.'})
    post(client, f'/api/salops/engagements/{engagement_id}/transition', ops, {
        'status': 'Active', 'reason': 'Readiness complete.', 'member_status_summary': 'Authorized support is active.',
    })
    task = post(client, f'/api/salops/engagements/{engagement_id}/tasks', ops, {
        'title': 'Exercise recovery path', 'instructions': 'CONTROLLED TASK INSTRUCTIONS',
        'assigned_to': 'CLIENT VALUE IGNORED', 'priority': 'Priority', 'assignment_id': assignment['id'],
    })
    assert task['assigned_to'] == 'Acceptance Assigned Expert'
    post(client, f"/api/salops/tasks/{task['id']}/transition", expert, {'status': 'In Progress', 'reason': 'Assigned expert began work.'})
    post(client, f"/api/salops/tasks/{task['id']}/transition", expert, {
        'status': 'Completed', 'reason': 'Exercise completed.', 'result_summary': 'Recovery path exercised successfully.',
    })
    report = post(client, f'/api/salops/engagements/{engagement_id}/field-reports', expert, {
        'task_id': task['id'], 'report_type': 'Completion Update', 'occurred_at': '2026-09-11T10:00:00Z',
        'member_summary': 'The authorized recovery exercise completed successfully.',
        'internal_details': 'CONTROLLED TACTICS PERSONNEL LOCATION COMMUNICATIONS',
    })
    post(client, f"/api/salops/field-reports/{report['id']}/release", reviewer, {'reason': 'Member summary independently reviewed.'})
    expense = post(client, f'/api/salops/engagements/{engagement_id}/expenses', intel, {
        'task_id': task['id'], 'category': 'Labor', 'description': 'CONTROLLED VENDOR AND RECEIPT DETAIL',
        'member_description': 'Authorized recovery support', 'vendor': 'CONTROLLED VENDOR',
        'incurred_on': '2026-09-11', 'amount': '900.00', 'currency': 'USD', 'reimbursable': True,
    })
    post(client, f"/api/salops/expenses/{expense['id']}/transition", intel, {'status': 'Submitted', 'reason': 'Expense submitted.'})
    post(client, f"/api/salops/expenses/{expense['id']}/transition", ops, {'status': 'Approved', 'reason': 'Expense independently reviewed.'})
    post(client, f'/api/salops/engagements/{engagement_id}/transition', ops, {
        'status': 'Demobilizing', 'reason': 'Delivery complete.', 'member_status_summary': 'Operations are demobilizing.',
    })
    post(client, f'/api/salops/engagements/{engagement_id}/transition', ops, {
        'status': 'Closed', 'reason': 'Objectives and records reconciled.', 'member_status_summary': 'The engagement is complete.',
    })
    statement = post(client, f'/api/salops/engagements/{engagement_id}/invoice-statements', ops, {
        'billing_period_start': '2026-09-10', 'billing_period_end': '2026-09-11',
        'service_summary': 'Authorized recovery support completed.',
    })
    post(client, f"/api/salops/invoice-statements/{statement['id']}/transition", reviewer, {'status': 'Reviewed', 'reason': 'Statement reviewed.'})
    post(client, f"/api/salops/invoice-statements/{statement['id']}/transition", admin, {'status': 'Approved', 'reason': 'Statement independently approved.'})
    post(client, f"/api/salops/invoice-statements/{statement['id']}/transition", admin, {'status': 'Released', 'reason': 'Approved statement released.'})

    released_report = post(client, f'/api/reports/{assessment_id}', thira)
    post(client, f"/api/reports/versions/{released_report['id']}/transition", reviewer, {'status': 'Reviewed', 'reason': 'Report reviewed.'})
    post(client, f"/api/reports/versions/{released_report['id']}/transition", member_authority, {'status': 'Approved', 'reason': 'Member authority approved.'})
    post(client, f"/api/reports/versions/{released_report['id']}/transition", admin, {'status': 'Released', 'reason': 'Approved report released.'})

    readiness_response = client.get('/api/salcapa/common-operating-picture', headers=member_authority)
    assert readiness_response.status_code == 200
    readiness = readiness_response.json()['protective_readiness']
    assert readiness['source'] == 'persisted_server_controlled_records'
    assert readiness['promise'] == 'See, Decide, Coordinate, Act, and Prove progress from an unverified condition toward demonstrated protective assurance.'
    assert [stage['key'] for stage in readiness['stages']] == ['see', 'decide', 'coordinate', 'act', 'prove']
    assert readiness['trace']['coordination_threads'] >= 1
    assert 'not a conclusion that the organization is unsafe' in readiness['stages'][0]['description']
    assert 'Light green' in readiness['stages'][3]['description']
    assert 'not absolute safety' in readiness['stages'][4]['description']
    assert readiness['trace']['qualified_signals'] >= 1
    assert readiness['trace']['assessed_capability_gaps'] >= 1
    assert readiness['trace']['prioritized_improvements'] >= 1
    assert readiness['trace']['executive_decisions'] >= 1
    assert readiness['trace']['authorized_actions'] >= 1
    assert readiness['trace']['completed_actions'] >= 1
    assert readiness['trace']['released_proof_records'] >= 2
    briefing = client.get(f'/api/report/{assessment_id}/executive.html', headers=member_authority)
    assert briefing.status_code == 200
    assert 'SalCAPA Protective Readiness Executive Briefing' in briefing.text
    assert 'informed by recognized THIRA principles' in briefing.text
    product_copy = (ROOT / 'static' / 'app.js').read_text()
    assert 'Work that needs attention' in product_copy
    assert 'Coordinate action &gt;' in product_copy

    member_payload = json.dumps({
        'cop': client.get('/api/salcapa/common-operating-picture', headers=member_authority).json(),
        'engagements': client.get('/api/salops/engagements', headers=member_authority).json(),
        'field_reports': client.get(f'/api/salops/engagements/{engagement_id}/field-reports', headers=member_authority).json(),
        'financials': client.get(f'/api/salops/engagements/{engagement_id}/financials', headers=member_authority).json(),
        'statements': client.get(f'/api/salops/engagements/{engagement_id}/invoice-statements', headers=member_authority).json(),
    })
    for forbidden in ('CONTROLLED SOURCE', 'CONTROLLED MEMBER LOCATION', 'CONTROLLED REPORTER',
                      'CONTROLLED OPERATING LOCATION', 'CONTROLLED OPERATIONS LEAD', 'CONTROLLED COMMUNICATIONS',
                      'CONTROLLED PERSONNEL', 'CONTROLLED READINESS', 'CONTROLLED TASK', 'CONTROLLED TACTICS',
                      'CONTROLLED VENDOR', 'CONTROLLED PRICING'):
        assert forbidden not in member_payload, forbidden

    backup = post(client, '/api/admin/backups', admin)
    assert post(client, f"/api/admin/backups/{backup['id']}/verify", admin)['ok']
    assert post(client, f"/api/admin/backups/{backup['id']}/dr-validate", admin)['ok']
    restore_request = post(client, '/api/admin/restore-requests', admin, {
        'backup_id': backup['id'], 'scope': 'Tenant 1 authoritative records', 'reason': 'Operating-model recovery exercise.',
    })
    post(client, f"/api/admin/restore-requests/{restore_request['id']}/decision", admin, {
        'decision': 'Authorized', 'reason': 'Self authorization is forbidden.'
    }, 409)
    post(client, f"/api/admin/restore-requests/{restore_request['id']}/decision", recovery, {
        'decision': 'Authorized', 'reason': 'Independent recovery authority approved the validated scope.'
    })

    conn = app.db()
    records = collect_tenant_records(conn, 1)
    errors = validate_records(records, 1)
    authority_denials = conn.execute("SELECT COUNT(*) c FROM security_events WHERE tenant_id=1 AND event_type='MEMBER_AUTHORITY_DENIED'").fetchone()['c']
    event_versions = [r['version_no'] for r in conn.execute("SELECT version_no FROM expert_events WHERE record_type='expert_assignment' AND record_id=? ORDER BY version_no", (assignment['id'],))]
    conn.close()
    assert not errors, errors
    assert authority_denials == 2
    assert event_versions == list(range(1, len(event_versions) + 1))
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = conn.execute(
        'SELECT COUNT(*) c FROM ops_invoice_statements WHERE tenant_id=1 AND id=? AND status=\'Released\'',
        (statement['id'],),
    ).fetchone()['c']
    restored_reports = conn.execute(
        'SELECT COUNT(*) c FROM report_versions WHERE tenant_id=1 AND id=? AND status=\'Released\'',
        (released_report['id'],),
    ).fetchone()['c']
    conn.close()
    assert restored == 1 and restored_reports == 1
    assert client.get('/api/salcapa/common-operating-picture', headers=auditor).status_code == 200
    condition_css = (ROOT / 'static' / 'condition-visuals.css').read_text(encoding='utf-8')
    guidance_css = (ROOT / 'static' / 'guidance.css').read_text(encoding='utf-8')
    readability_css = (ROOT / 'static' / 'readability.css').read_text(encoding='utf-8')
    contextual_css = (ROOT / 'static' / 'salcapa-contextual-guidance.css').read_text(encoding='utf-8')
    mission_css = (ROOT / 'static' / 'mission-map.css').read_text(encoding='utf-8')
    styles_css = (ROOT / 'static' / 'styles.css').read_text(encoding='utf-8')
    guidance_js = (ROOT / 'static' / 'guidance.js').read_text(encoding='utf-8')
    required_tokens = (
        '--salcapa-stage-see', '--salcapa-stage-decide', '--salcapa-stage-coordinate',
        '--salcapa-stage-act', '--salcapa-stage-prove',
    )
    assert all(token in condition_css for token in required_tokens)
    for stylesheet in (guidance_css, readability_css, contextual_css, mission_css, styles_css):
        assert all(f'var({token})' in stylesheet for token in required_tokens), token
    assert 'aria-current="step"' in guidance_js
    assert 'Light green — approved protective action is underway' in guidance_js
    assert 'Full green — current evidence demonstrates the highest reasonably achievable protective condition within scope, not absolute safety' in guidance_js

    print('SALCAPA_OPERATING_MODEL_ACCEPTANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
