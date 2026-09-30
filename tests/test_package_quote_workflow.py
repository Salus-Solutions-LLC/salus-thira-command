"""Quote and acceptance guardrails in an isolated local database."""

import os
import subprocess
import sys
import textwrap


def test_level_one_quote_requires_review_and_exact_member_acceptance(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'candidate.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'prototype',
        'SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED': '1',
        'PYTHONPATH': os.getcwd(),
    })
    program = textwrap.dedent('''
        from fastapi.testclient import TestClient
        import app
        director = TestClient(app.app, headers={'X-Salus-Role':'Assessment Director'})
        response = director.post('/api/assessments',json={
            'name':'Single site review','organization':'Example Member',
            'covered_operation':'One named operation','exclusions':'Other sites and functions',
            'requested_package_level':1,'requested_scope_band':'A',
            'requested_access_variant':'Access',
        })
        assert response.status_code == 200, response.text
        assessment_id = response.json()['id']
        quote = dict(assessment_version=1,level=1,band='A',variant='Access',
            covered_operation='One named operation',exclusions='Other sites and functions',
            scope_basis='Reviewed one decision unit and basic records',decision_owner='Director',
            source_receipt_id='SPA-EXAMPLE',fee_cents=150000,currency='USD',
            valid_until='2099-01-01',capacity_confirmed=True,
            access_eligibility_confirmed=True,access_eligibility_basis='One simple operation',
            agreement_reference='AGREEMENT-1',agreement_sha256='a'*64,
            separate_services_excluded=True)
        url=f'/api/assessments/{assessment_id}/package-quote'
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED=False
        assert director.post(url,json=quote).status_code==503
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED=True
        app.ENVIRONMENT='production'
        assert director.post(url,json=quote).status_code==503
        app.ENVIRONMENT='development'
        bad=director.post(url,json={**quote,'access_eligibility_confirmed':False})
        assert bad.status_code == 422, bad.text
        response=director.post(url,json=quote)
        assert response.status_code == 200, response.text
        issued=response.json()
        assert issued['fee_cents']==150000 and issued['version_no']==1
        assert director.get(url).json()['status']=='Quoted'
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET fee_cents=? WHERE id=?',(150001,issued['id']))
        conn.commit(); conn.close()
        assert director.get(url).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET fee_cents=? WHERE id=?',(150000,issued['id']))
        conn.commit(); conn.close()
        acceptance=dict(quote_id=issued['id'],quote_sha256=issued['content_sha256'],
            agreement_sha256='a'*64,member_authority_basis='Authorized Member executive',
            idempotency_key='member-acceptance-0001',accept_quote_and_agreement=True)
        assert director.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance).status_code==403
        conn=app.db()
        user_id=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'member-exec','Member Executive','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (user_id,app._hash_token('test-cookie'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit(); conn.close()
        app.AUTH_MODE='session'
        member=TestClient(app.app,cookies={'salus_session':'test-cookie'})
        stale=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json={**acceptance,'quote_sha256':'b'*64})
        assert stale.status_code==409, stale.text
        accepted=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert accepted.status_code==200, accepted.text
        assert accepted.json()['status']=='Authorized'
        retry=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert retry.status_code==200 and retry.json()['idempotent'] is True, retry.text
        assert member.get(url).json()['status']=='Authorized'
        assert director.post(url,json=quote).status_code==401
        app.AUTH_MODE='prototype'
        assert director.post(url,json=quote).status_code==409
        other_tenant=TestClient(app.app,headers={'X-Salus-Role':'Assessment Director','X-Salus-Tenant':'2'})
        assert other_tenant.get(url).status_code==403
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==1
        from portable_backup import collect_tenant_records, replace_tenant_records, validate_records
        records=collect_tenant_records(conn,1)
        assert len(records['package_quote_versions'])==1
        assert len(records['package_acceptances'])==1
        assert not validate_records(records,1)
        replace_tenant_records(conn,1,records)
        conn.commit()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==1
        conn.close()
    ''')
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
