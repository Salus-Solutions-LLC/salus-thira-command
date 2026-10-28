"""A pinned staff pilot can see one paid buyer assessment, never generic tenant data."""

import os
import subprocess
import sys
import textwrap


def test_exact_pinned_staff_scope_and_other_tenant_denial(tmp_path):
    env=os.environ.copy()
    env.update(SALUS_DB_PATH=str(tmp_path/'staff-scope.db'),
               SALUS_LOCAL_STORAGE_DIR=str(tmp_path/'files'),
               SALUS_BACKUP_DIR=str(tmp_path/'backups'),
               SALUS_SEED_DEMO='0',SALUS_AUTH_MODE='oidc',
               PYTHONPATH=os.pathsep.join(filter(None,(os.getcwd(),env.get('PYTHONPATH','')))))
    code=textwrap.dedent('''
        from fastapi.testclient import TestClient
        import app

        conn=app.db()
        ts=app.now()
        staff_id=conn.execute(''' + "'''" + '''INSERT INTO users
            (tenant_id,username,display_name,role,sensitivity_clearance,status,
             created_at,updated_at,email,external_subject,identity_provider)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)''' + "'''" + ''',
            (1,'staff-owner','Fictional Staff Owner','System Administrator',
             'Highly Sensitive','Active',ts,ts,'staff@example.test',
             'pinned-staff-object','entra')).lastrowid
        conn.execute(''' + "'''" + '''INSERT INTO auth_sessions
            (user_id,token_hash,expires_at,created_at,last_seen_at)
            VALUES(?,?,?,?,?)''' + "'''" + ''',
            (staff_id,app._hash_token('staff-cookie'),
             '2099-01-01T00:00:00Z',ts,ts))
        linked=[]
        for number in (1,2):
            tid=conn.execute('INSERT INTO tenants(name,slug,status,created_at) '
                'VALUES(?,?,?,?)',(f'Fictional buyer {number}',
                f'fictional-buyer-{number}','Active',ts)).lastrowid
            buyer_id=conn.execute(''' + "'''" + '''INSERT INTO users
                (tenant_id,username,display_name,role,status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?)''' + "'''" + ''',
                (tid,f'buyer-{number}',f'Fictional Buyer {number}',
                 'Client Executive','Active',ts,ts)).lastrowid
            assessment_id=conn.execute(''' + "'''" + '''INSERT INTO assessments
                (tenant_id,name,organization,created_at,updated_at)
                VALUES(?,?,?,?,?)''' + "'''" + ''',
                (tid,f'Site {number}',f'Fictional Organization {number}',ts,ts)).lastrowid
            order_id=conn.execute(''' + "'''" + '''INSERT INTO level1a_orders
                (tenant_id,buyer_user_id,idempotency_key,scope_version,buyer_legal_name,
                 unit_kind,unit_name,covered_boundary,operating_activity,exclusions,
                 decision_owner_role,notice_email,service_use_address,
                 service_use_postal_code,use_country,use_region,scope_sha256,
                 status,created_at,updated_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''' + "'''" + ''',
                (tid,buyer_id,f'fictional-{number}',1,f'Fictional Organization {number}',
                 'Site',f'Site {number}','One site','Operations','Other sites',
                 'Executive',f'buyer-{number}@example.test','1 Test Street','78701',
                 'US','TX',f'scope-{number}','Paid',ts,ts)).lastrowid
            conn.execute(''' + "'''" + '''INSERT INTO level1a_assessment_links
                (tenant_id,buyer_user_id,order_id,assessment_id,acceptance_id,
                 scope_sha256,agreement_sha256,receipt_sha256,created_at)
                VALUES(?,?,?,?,?,?,?,?,?)''' + "'''" + ''',
                (tid,buyer_id,order_id,assessment_id,1,f'scope-{number}',
                 f'agreement-{number}',f'receipt-{number}',ts))
            linked.append((tid,assessment_id,order_id))
        conn.commit();conn.close()
        one,two=linked
        app.LEVEL1A_SOLO_REVIEWER_EMAIL='staff@example.test'
        app.LEVEL1A_SOLO_REVIEWER_OBJECT_ID='pinned-staff-object'
        app.LEVEL1A_SOLO_REVIEW_ORDER_ID=str(one[2])
        staff=TestClient(app.app,cookies={'salus_session':'staff-cookie'})
        assert staff.get('/api/assessments').json()==[]
        available=staff.get('/api/level1a/staff/assessments')
        assert available.status_code==200,available.text
        assert [(x['id'],x['order_id']) for x in available.json()]==[(one[1],one[2])]
        observed=[]
        def verified(conn,assessment_id,assessment,request):
            observed.append((assessment_id,app.tenant_id(request)))
            return {'order_id':one[2],'buyer_user_id':1,'scope_sha256':'scope-1',
                'assessment_scope_sha256':'a','agreement_sha256':'agreement-1',
                'receipt_document_sha256':'receipt-1','record_sha256':'r'}
        app._verified_level1a_report_source=verified
        source=staff.get(f'/api/assessments/{one[1]}/level1a-report-source')
        assert source.status_code==200,source.text
        assert observed==[(one[1],one[0])]
        assert staff.get(f'/api/assessments/{two[1]}/level1a-report-source').status_code==403
        assert observed==[(one[1],one[0])]
        app.LEVEL1A_SOLO_REVIEWER_OBJECT_ID='wrong-object'
        assert staff.get('/api/level1a/staff/assessments').json()==[]
        assert staff.get(f'/api/assessments/{one[1]}/level1a-report-source').status_code==403
    ''')
    result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,
                          text=True,timeout=120)
    assert result.returncode==0,result.stdout+result.stderr
