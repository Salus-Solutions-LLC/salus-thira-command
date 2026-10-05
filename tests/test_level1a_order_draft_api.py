"""A signed-in buyer gets one durable order, including a correction path."""

import os
import subprocess
import sys
import textwrap


def test_member_order_reference_and_tenant_boundary(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'orders.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_BACKUP_DIR': str(tmp_path / 'backups'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'session',
        'SALUS_LEVEL1A_ORDER_DRAFT_ENABLED': '1',
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent('''
        from fastapi.testclient import TestClient
        import app

        conn=app.db()
        other_tenant=conn.execute('INSERT INTO tenants(name,slug,status,created_at) VALUES(?,?,?,?)',
            ('Other Example','other-example','Active',app.now())).lastrowid
        users=[]
        for tid,name,role,token in ((1,'buyer-one','Client Executive','buyer-one-cookie'),
                                    (other_tenant,'buyer-two','Client Executive','buyer-two-cookie'),
                                    (1,'analyst','Lead Assessor','analyst-cookie')):
            uid=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                (tid,name,name,role,'Active',app.now(),app.now())).lastrowid
            conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
                (uid,app._hash_token(token),'2099-01-01T00:00:00Z',app.now(),app.now()))
            users.append(TestClient(app.app,cookies={'salus_session':token}))
        conn.commit();conn.close()
        buyer,other,analyst=users
        payload={'idempotency_key':'buyer-order-00000001',
            'buyer_legal_name':'Example Care LLC','unit_kind':'Site',
            'unit_name':'','covered_boundary':'One building and playground',
            'operating_activity':'Daycare','exclusions':'Other sites',
            'decision_owner_role':'Chief executive','notice_email':'buyer@example.test',
            'use_country':'US','use_region':'TX'}
        assert analyst.post('/api/level1a/orders',json=payload).status_code==403
        created=buyer.post('/api/level1a/orders',json=payload)
        assert created.status_code==200,created.text
        order=created.json()
        assert order['status']=='NeedsCorrection' and order['order_reference'].startswith('L1A-')
        assert order['base_price_cents']==150000
        assert not order['checkout_available'] and not order['upload_available']
        repeated=buyer.post('/api/level1a/orders',json=payload)
        assert repeated.status_code==200 and repeated.json()['order_id']==order['order_id']
        assert repeated.json()['idempotent'] is True
        url=f"/api/level1a/orders/{order['order_id']}"
        assert other.get(url).status_code==404
        fixed=buyer.patch(url,json={
            'expected_scope_version':1,'buyer_legal_name':'Example Care LLC',
            'unit_kind':'Site','unit_name':'Oak Street daycare',
            'covered_boundary':'One building and playground',
            'operating_activity':'Daycare','exclusions':'Other sites',
            'decision_owner_role':'Chief executive','notice_email':'buyer@example.test',
            'use_country':'US','use_region':'TX'})
        assert fixed.status_code==200,fixed.text
        assert fixed.json()['status']=='ReadyForAgreement'
        assert fixed.json()['scope_version']==2 and len(fixed.json()['scope_sha256'])==64
        assert other.patch(url,json={'expected_scope_version':2,
            'buyer_legal_name':'Other','unit_kind':'Site',
            'unit_name':'Other','covered_boundary':'Other',
            'operating_activity':'Other','exclusions':'Other',
            'decision_owner_role':'Chief executive','notice_email':'other@example.test',
            'use_country':'US','use_region':'TX'}).status_code==409
        assert buyer.patch(url,json={'expected_scope_version':1,
            'buyer_legal_name':'Example Care LLC','unit_kind':'Site',
            'unit_name':'Changed','covered_boundary':'One building and playground',
            'operating_activity':'Daycare','exclusions':'Other sites',
            'decision_owner_role':'Chief executive','notice_email':'buyer@example.test',
            'use_country':'US','use_region':'TX'}).status_code==409
        assert buyer.post('/api/assessments/1/package-checkout').status_code==503
        conn=app.db()
        record=conn.execute('SELECT tenant_id,buyer_user_id,scope_version FROM level1a_orders WHERE id=?',
            (order['order_id'],)).fetchone()
        assert record['tenant_id']==1 and record['scope_version']==2
        log=conn.execute("SELECT tenant_id FROM audit_log WHERE action='LEVEL1A_DRAFT_CREATE' AND entity_id=?",
            (order['order_id'],)).fetchone()
        assert log['tenant_id']==1
        conn.close()
    ''')
    run = subprocess.run([sys.executable, '-c', program], env=env,
                         cwd=os.getcwd(), capture_output=True, text=True, timeout=90)
    assert run.returncode == 0, run.stdout + run.stderr
