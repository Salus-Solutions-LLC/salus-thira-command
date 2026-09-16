#!/usr/bin/env python3
import os
import tempfile
from pathlib import Path

WORKSPACE = tempfile.TemporaryDirectory()
os.environ['SALUS_DB_BACKEND'] = 'sqlite'
os.environ['SALUS_DB_PATH'] = str(Path(WORKSPACE.name) / 'pilot-accounts.db')
os.environ['SALUS_BACKUP_DIR'] = str(Path(WORKSPACE.name) / 'backups')
os.environ['SALUS_LOCAL_STORAGE_DIR'] = str(Path(WORKSPACE.name) / 'attachments')
os.environ['SALUS_AUTH_MODE'] = 'prototype'
os.environ['SALUS_SEED_DEMO'] = '0'

from fastapi.testclient import TestClient
import app


def main():
    client = TestClient(app.app)
    admin = {
        'X-Salus-Tenant': '1',
        'X-Salus-Role': 'System Administrator',
        'X-Salus-User': 'Pilot Administrator',
    }
    member = {
        'X-Salus-Tenant': '1',
        'X-Salus-Role': 'Contributor',
        'X-Salus-User': 'Unauthorized Contributor',
    }

    denied = client.get('/api/admin/pilot/users', headers=member)
    assert denied.status_code == 403, denied.text

    tenant = client.post('/api/admin/pilot/tenants', headers=admin, json={
        'name': 'Early Access Organization',
        'slug': 'early-access-organization',
    })
    assert tenant.status_code == 200, tenant.text
    tenant_id = tenant.json()['id']

    invalid = client.post('/api/admin/pilot/users', headers=admin, json={
        'email': 'not-an-email',
        'display_name': 'Invalid User',
        'tenant_id': tenant_id,
        'role': 'Contributor',
        'sensitivity_clearance': 'Standard',
    })
    assert invalid.status_code == 422, invalid.text

    created = client.post('/api/admin/pilot/users', headers=admin, json={
        'email': 'pilot.member@example.test',
        'display_name': 'Pilot Member',
        'tenant_id': tenant_id,
        'role': 'Client Executive',
        'sensitivity_clearance': 'Sensitive',
    })
    assert created.status_code == 200, created.text
    user = created.json()
    assert user['email'] == 'pilot.member@example.test'
    assert user['tenant_id'] == tenant_id
    assert user['identity_provider'] == app.OIDC_PROVIDER_NAME
    assert user['identity_bound'] == 0

    duplicate = client.post('/api/admin/pilot/users', headers=admin, json={
        'email': 'PILOT.MEMBER@EXAMPLE.TEST',
        'display_name': 'Duplicate Member',
        'tenant_id': tenant_id,
        'role': 'Contributor',
        'sensitivity_clearance': 'Standard',
    })
    assert duplicate.status_code == 409, duplicate.text

    conn = app.db()
    assessment = conn.execute(
        """INSERT INTO assessments
           (tenant_id,name,organization,assessment_type,purpose,mission,scope,status,
            executive_sponsor,assessment_director,lead_assessor,start_date,target_completion,
            reassessment_date,classification,scope_locked,version,created_at,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tenant_id,'Pilot Assessment','Early Access Organization','THIRA','Pilot','Protect',
         'Bounded pilot','Draft','Executive','Director','Assessor','','','','Standard',0,1,
         app.now(),app.now()),
    )
    assessment_id = assessment.lastrowid
    conn.commit()
    conn.close()

    access = client.post(
        f"/api/admin/pilot/users/{user['id']}/assessment-access",
        headers=admin,
        json={'assessment_ids': [assessment_id], 'role_override': '', 'sensitivity_clearance': 'Sensitive'},
    )
    assert access.status_code == 200, access.text
    assert access.json()['assessment_ids'] == [assessment_id]

    conn = app.db()
    token_hash = app._hash_token('pilot-active-session')
    conn.execute(
        "INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)",
        (user['id'], token_hash, '2099-01-01T00:00:00Z', app.now(), app.now()),
    )
    conn.commit()
    conn.close()

    disabled = client.post(
        f"/api/admin/pilot/users/{user['id']}/status",
        headers=admin,
        json={'status': 'Disabled'},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()['sessions_revoked'] is True

    conn = app.db()
    assert conn.execute("SELECT status FROM users WHERE id=?", (user['id'],)).fetchone()['status'] == 'Disabled'
    assert conn.execute("SELECT COUNT(*) c FROM auth_sessions WHERE user_id=?", (user['id'],)).fetchone()['c'] == 0
    assert conn.execute("SELECT COUNT(*) c FROM assessment_access WHERE user_id=?", (user['id'],)).fetchone()['c'] == 1
    events = [r['action'] for r in conn.execute(
        "SELECT action FROM audit_log WHERE action LIKE 'PILOT_%' ORDER BY id"
    )]
    conn.close()
    assert 'PILOT_TENANT_CREATE' in events
    assert 'PILOT_USER_PREAUTHORIZE' in events
    assert 'PILOT_USER_ASSESSMENT_ACCESS' in events
    assert 'PILOT_USER_STATUS' in events

    source = Path(app.__file__).read_text(encoding='utf-8')
    assert 'OIDC_PREAUTHORIZED_IDENTITY_BOUND' in source
    assert "external_subject=''" in source
    ui = (Path(app.__file__).parent / 'static' / 'app.js').read_text(encoding='utf-8')
    for marker in ('Early-Access Accounts','Preauthorize user','Identity Bound','Invitation Pending'):
        assert marker in ui, marker

    print('SALCAPA_EARLY_ACCESS_ACCOUNTS_PASS')


if __name__ == '__main__':
    main()
