"""A protected pilot can transact only as its verified external buyer inbox."""

import os
import subprocess
import sys
import textwrap


def test_level1a_pilot_blocks_other_buyers_and_workforce(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'pilot.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_BACKUP_DIR': str(tmp_path / 'backups'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'session',
        'SALUS_LEVEL1A_ORDER_DRAFT_ENABLED': '1',
        'SALUS_LEVEL1A_PILOT_EMAIL': 'pilot@example.test',
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent('''
        from fastapi.testclient import TestClient
        import app

        conn = app.db()
        clients = []
        for username, email, provider, token in (
            ('pilot', 'Pilot@Example.Test', app.CUSTOMER_PROVIDER, 'pilot-cookie'),
            ('other', 'other@example.test', app.CUSTOMER_PROVIDER, 'other-cookie'),
            ('staff', 'pilot@example.test', 'entra', 'staff-cookie'),
        ):
            uid = conn.execute(
                'INSERT INTO users(tenant_id,username,display_name,role,status,'
                'created_at,updated_at,email,identity_provider) VALUES(?,?,?,?,?,?,?,?,?)',
                (1, username, username, 'Client Executive', 'Active',
                 app.now(), app.now(), email, provider)).lastrowid
            conn.execute(
                'INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)'
                ' VALUES(?,?,?,?,?)',
                (uid, app._hash_token(token), '2099-01-01T00:00:00Z',
                 app.now(), app.now()))
            clients.append(TestClient(app.app, cookies={'salus_session': token}))
        conn.commit()
        conn.close()
        payload = {
            'idempotency_key': 'pilot-order-00000001',
            'buyer_legal_name': 'Fictional Pilot LLC', 'unit_kind': 'Site',
            'unit_name': 'One fictional site', 'covered_boundary': 'One site',
            'operating_activity': 'Fictional service', 'exclusions': 'Other sites',
            'decision_owner_role': 'Chief executive',
            'notice_email': 'pilot@example.test',
            'service_use_address': '100 Oak Street, Austin, Texas',
            'service_use_postal_code': '78701', 'use_country': 'US',
            'use_region': 'TX',
        }
        pilot, other, staff = clients
        assert other.post('/api/level1a/orders', json=payload).status_code == 403
        assert staff.post('/api/level1a/orders', json=payload).status_code == 403
        accepted = pilot.post('/api/level1a/orders', json=payload)
        assert accepted.status_code == 200, accepted.text
        conn = app.db()
        assert conn.execute('SELECT COUNT(*) FROM level1a_orders').fetchone()[0] == 1
        conn.close()
    ''')
    run = subprocess.run([sys.executable, '-c', program], env=env,
                         cwd=os.getcwd(), capture_output=True, text=True, timeout=90)
    assert run.returncode == 0, run.stdout + run.stderr
