#!/usr/bin/env python3
import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = tempfile.TemporaryDirectory()
os.environ.setdefault('SALUS_DB_BACKEND', 'sqlite')
os.environ.setdefault('SALUS_DB_PATH', str(Path(WORKSPACE.name) / 'salcapa-v25.db'))
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


def observation(title, choice='Identified'):
    return {
        'reporter_choice': choice,
        'reporter_name': '' if choice == 'Anonymous' else 'Protected Reporter',
        'reporter_contact': '' if choice == 'Anonymous' else 'reporter@example.test',
        'report_on_behalf_of': '', 'title': title,
        'narrative': 'Observed activity requiring professional review.',
        'location': 'Member-reported location', 'observed_at': '2026-09-04T04:00:00Z',
        'context': 'Submitted for accountable triage.', 'reported_urgency': 'Urgent',
        'emergency_acknowledged': True,
    }


def advance_to_triage(client, oid, analyst, coordinator):
    post(client, f'/api/observations/{oid}/acknowledge', analyst, {'reason': 'Receipt confirmed; source remains unverified'})
    post(client, f'/api/observations/{oid}/triage', coordinator, {
        'category': 'Security Concern', 'priority': 'Priority',
        'assigned_to': 'Protective Intelligence Team', 'notes': 'Requires governed professional evaluation',
    })


def main():
    client = TestClient(app.app)
    admin = {'X-Salus-Role': 'System Administrator', 'X-Salus-User': 'System Administrator', 'X-Salus-Tenant': '1'}
    analyst = {**admin, 'X-Salus-Role': 'Lead Assessor', 'X-Salus-User': 'SalINTEL Analyst'}
    coordinator = {**admin, 'X-Salus-Role': 'Assessment Director', 'X-Salus-User': 'Triage Coordinator'}
    contributor = {**admin, 'X-Salus-Role': 'Contributor', 'X-Salus-User': 'Protected Member Reporter'}
    other_member = {**contributor, 'X-Salus-User': 'Different Protected Member'}
    executive = {**admin, 'X-Salus-Role': 'Client Executive', 'X-Salus-User': 'Protected Member Authority'}
    auditor = {**admin, 'X-Salus-Role': 'Auditor', 'X-Salus-User': 'Independent Auditor'}

    forged_channel = client.post('/api/observation-channels', headers=admin, json={
        'name': 'Public reporting', 'expires_at': '2026-12-31T23:59:59Z', 'tenant_id': 99, 'status': 'Active', 'token_hash': 'forged',
    })
    assert forged_channel.status_code == 422
    channel = post(client, '/api/observation-channels', admin, {
        'name': 'Approved public observation intake', 'expires_at': '2026-12-31T23:59:59Z',
    })
    token = channel['channel_token']
    assert len(token) >= 32 and 'token_hash' not in channel
    listed_channels = client.get('/api/observation-channels', headers=admin).json()
    assert len(listed_channels) == 1 and 'token_hash' not in listed_channels[0] and 'channel_token' not in listed_channels[0]
    assert client.get('/api/observation-channels', headers=analyst).status_code == 403

    emergency = observation('Emergency acknowledgement required')
    emergency['emergency_acknowledged'] = False
    assert client.post('/api/observations', headers=contributor, json=emergency).status_code == 422
    forged = {**observation('Forged lifecycle'), 'tenant_id': 2, 'status': 'Routed', 'triage_priority': 'Critical', 'assigned_to': 'forged'}
    assert client.post('/api/observations', headers=contributor, json=forged).status_code == 422

    member_observation = post(client, '/api/observations', contributor, observation('Member-reported concern'))
    member_id = member_observation['id']
    assert member_observation['status'] == 'Submitted'
    assert not {'reporter_name', 'reporter_contact', 'narrative', 'source_protection', 'receipt_hash'} & set(member_observation)
    assert client.get('/api/observations', headers=other_member).json() == []
    executive_rows = client.get('/api/observations', headers=executive).json()
    assert len(executive_rows) == 1 and 'reporter_contact' not in executive_rows[0]
    audit_rows = client.get('/api/observations', headers=auditor).json()
    assert len(audit_rows) == 1 and 'narrative' not in audit_rows[0] and 'reporter_name' not in audit_rows[0]
    assert client.get('/api/observations', headers={**admin, 'X-Salus-Tenant': '2'}).json() == []
    assert client.post(f'/api/observations/{member_id}/acknowledge', headers={**analyst, 'X-Salus-Tenant': '2'}, json={'reason': 'cross tenant'}).status_code == 403

    upload = client.post(f'/api/observations/{member_id}/attachments', headers=contributor, files={'file': ('observation.txt', io.BytesIO(b'controlled observation attachment'), 'text/plain')})
    assert upload.status_code == 200, upload.text
    attachment = upload.json()
    assert attachment['scan_status'] in {'Clean', 'Not Configured'} and 'stored_name' not in attachment and 'scan_detail' not in attachment
    assert client.get(f'/api/observation-attachments/{attachment["id"]}/download', headers=other_member).status_code == 403
    downloaded = client.get(f'/api/observation-attachments/{attachment["id"]}/download', headers=contributor)
    assert downloaded.status_code == 200 and downloaded.content == b'controlled observation attachment'
    assert client.get(f'/api/observation-attachments/{attachment["id"]}/download', headers=auditor).status_code == 403

    assert post(client, f'/api/observations/{member_id}/acknowledge', contributor, {'reason': 'Forged member acknowledgement'}, 403)
    assert post(client, f'/api/observations/{member_id}/triage', analyst, {
        'category': 'Security Concern', 'priority': 'Priority', 'assigned_to': 'Analyst', 'notes': 'Out of order',
    }, 409)
    baseline_intel = len(client.get('/api/salintel/findings', headers=analyst).json())
    baseline_ops = len(client.get('/api/salops/requests', headers=analyst).json())
    advance_to_triage(client, member_id, analyst, coordinator)
    routed_intel = post(client, f'/api/observations/{member_id}/route', analyst, {
        'target': 'SalINTEL', 'assessment_id': 1, 'member_summary': 'Concern referred for intelligence evaluation.',
        'reason': 'Authorized analyst review required', 'external_reference': '',
    })
    assert routed_intel['status'] == 'Routed' and routed_intel['routed_record_type'] == 'intel_finding'
    assert len(client.get('/api/salintel/findings', headers=analyst).json()) == baseline_intel + 1
    assert post(client, f'/api/observations/{member_id}/route', analyst, {
        'target': 'SalOPS', 'assessment_id': 1, 'member_summary': 'Duplicate route', 'reason': 'forged', 'external_reference': '',
    }, 409)
    assert client.post(f'/api/observations/{member_id}/attachments', headers=contributor, files={'file': ('late.txt', b'late', 'text/plain')}).status_code == 409
    closed = post(client, f'/api/observations/{member_id}/close', coordinator, {'disposition': 'Referred', 'reason': 'SalINTEL referral recorded'})
    assert closed['status'] == 'Closed'

    public_payload = observation('Anonymous public concern', 'Anonymous')
    public_headers = {'X-Salus-Observation-Channel': token}
    assert client.post('/api/public/observations', headers={'X-Salus-Observation-Channel': 'invalid'}, json=public_payload).status_code == 404
    public_response = post(client, '/api/public/observations', public_headers, public_payload)
    receipt = public_response['receipt_token']; public_key = public_response['record_key']
    public_rows = client.get('/api/observations', headers=analyst).json()
    public_row = next(x for x in public_rows if x['record_key'] == public_key); public_id = public_row['id']
    assert public_row['source_protection'] == 'Salus Restricted' and public_row['reporter_name'] == ''
    assert 'receipt_hash' not in public_row and all(x['record_key'] != public_key for x in client.get('/api/observations', headers=executive).json())
    bad_upload = client.post(f'/api/public/observations/{public_key}/attachments', headers={**public_headers, 'X-Salus-Observation-Receipt': 'wrong'}, files={'file': ('public.txt', b'public observation', 'text/plain')})
    assert bad_upload.status_code == 404
    public_upload = client.post(f'/api/public/observations/{public_key}/attachments', headers={**public_headers, 'X-Salus-Observation-Receipt': receipt}, files={'file': ('public.txt', b'public observation', 'text/plain')})
    assert public_upload.status_code == 200, public_upload.text
    advance_to_triage(client, public_id, analyst, coordinator)
    routed_ops = post(client, f'/api/observations/{public_id}/route', coordinator, {
        'target': 'SalOPS', 'assessment_id': 1, 'member_summary': 'Member-safe operational review requested.',
        'reason': 'Triage established an operational review need', 'external_reference': '',
    })
    assert routed_ops['routed_record_type'] == 'ops_request'
    assert len(client.get('/api/salops/requests', headers=analyst).json()) == baseline_ops + 1

    thira_observation = post(client, '/api/observations', contributor, observation('Assessment concern'))
    advance_to_triage(client, thira_observation['id'], analyst, coordinator)
    assert post(client, f'/api/observations/{thira_observation["id"]}/route', coordinator, {
        'target': 'SalTHIRA', 'assessment_id': None, 'member_summary': 'Assessment required', 'reason': 'Missing assessment test', 'external_reference': '',
    }, 422)
    routed_thira = post(client, f'/api/observations/{thira_observation["id"]}/route', coordinator, {
        'target': 'SalTHIRA', 'assessment_id': 1, 'member_summary': 'Reassess relevant protective conditions.',
        'reason': 'Authorized assessment referral', 'external_reference': '',
    })
    assert routed_thira['routed_record_type'] == 'reassessment_trigger'

    external = post(client, '/api/observations', contributor, observation('External referral concern'))
    advance_to_triage(client, external['id'], analyst, coordinator)
    assert post(client, f'/api/observations/{external["id"]}/route', coordinator, {
        'target': 'External Escalation', 'assessment_id': None, 'member_summary': 'Recorded referral.',
        'reason': 'External authority determined by reviewer', 'external_reference': '',
    }, 422)
    external_routed = post(client, f'/api/observations/{external["id"]}/route', coordinator, {
        'target': 'External Escalation', 'assessment_id': None, 'member_summary': 'Recorded referral.',
        'reason': 'External authority determined by reviewer', 'external_reference': 'CASE-EXT-2026-001',
    })
    assert external_routed['routed_record_id'] is None and external_routed['disposition'] == 'CASE-EXT-2026-001'

    governed = client.patch(f'/api/observations/{public_id}/governance', headers=coordinator, json={'legal_hold': True, 'retention_until': '2030-01-01T00:00:00Z'})
    assert governed.status_code == 200 and governed.json()['legal_hold'] == 1
    conn = app.db()
    propagated = conn.execute('SELECT legal_hold,retention_until FROM observation_attachments WHERE observation_id=?',(public_id,)).fetchone()
    records = collect_tenant_records(conn, 1)
    event_versions = [r['version_no'] for r in records['observation_events'] if r['observation_id'] == member_id]
    audit_tenants = {r['tenant_id'] for r in conn.execute("SELECT tenant_id FROM audit_log WHERE entity_type IN ('observation','observation_attachment','observation_intake_channel')")}
    boundary_events = conn.execute("SELECT COUNT(*) c FROM security_events WHERE event_type='OBSERVATION_TENANT_BOUNDARY_VIOLATION'").fetchone()['c']
    conn.close()
    assert propagated['legal_hold'] == 1 and propagated['retention_until'] == '2030-01-01T00:00:00Z'
    assert event_versions == list(range(1, len(event_versions) + 1)) and len(event_versions) == 5
    assert validate_records(records, 1) == [] and audit_tenants == {1} and boundary_events == 1
    conn = app.db(); replace_tenant_records(conn, 1, records); conn.commit()
    restored = conn.execute('SELECT COUNT(*) c FROM observations WHERE tenant_id=1').fetchone()['c']
    restored_attachments = conn.execute('SELECT COUNT(*) c FROM observation_attachments WHERE tenant_id=1').fetchone()['c']; conn.close()
    assert restored == 4 and restored_attachments == 2

    post(client, f'/api/observation-channels/{channel["id"]}/disable', admin, {'reason': 'Validation channel retired'})
    assert client.post('/api/public/observations', headers=public_headers, json=observation('Disabled channel')).status_code == 404
    print('SALCAPA_V25_OBSERVATION_GOVERNANCE_PASS', app.DB_BACKEND)


if __name__ == '__main__':
    main()
