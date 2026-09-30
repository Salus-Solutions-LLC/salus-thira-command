"""A prospect handoff stays unapproved and is erased when the prospect deletes it."""

import os
import subprocess
import sys
import textwrap


def test_consent_claim_and_prospect_deletion(tmp_path):
    env = os.environ.copy()
    env.update({
        'SALUS_DB_PATH': str(tmp_path / 'handoff.db'),
        'SALUS_LOCAL_STORAGE_DIR': str(tmp_path / 'attachments'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'prototype',
        'SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED': '1',
        'PYTHONPATH': os.getcwd(),
    })
    program = textwrap.dedent("""
        import json
        from fastapi.testclient import TestClient
        import app
        import public_protection_advisor as advisor

        director=TestClient(app.app,headers={'X-Salus-Role':'Assessment Director'})
        created=director.post('/api/assessments',json={
            'name':'One scope','organization':'Example Member',
            'covered_operation':'One operation','exclusions':'Other operations',
            'requested_package_level':1,'requested_scope_band':'A',
            'requested_access_variant':'Access'})
        assert created.status_code==200,created.text
        assessment_id=created.json()['id']
        conn=app.db()
        session='SPA-SESSION-TEST'; account='SPA-ACCOUNT-TEST'
        submission='SPA-SUBMISSION-TEST'; receipt='SPA-RECEIPT-TEST'
        conn.execute('''INSERT INTO advisor_public_sessions
          (session_key,token_sha256,csrf_sha256,organization_type,primary_consent,
           secondary_deidentified_consent,consent_notice_version,retention_policy_version,
           questionnaire_version,status,created_at,expires_at,submitted_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
           (session,advisor._sha('session-cookie'),advisor._sha('csrf'),'Business',1,0,
            'consent-v1','retention-v1','questions-v1','Submitted',app.now(),'2099-01-01T00:00:00Z',app.now()))
        conn.execute('''INSERT INTO advisor_public_accounts
          (account_key,email,password_salt,password_hash,status,created_at,email_verified_at)
          VALUES(?,?,?,?,?,?,?)''',(account,'member@example.org','salt','hash','Active',app.now(),app.now()))
        conn.execute('''INSERT INTO advisor_public_account_sessions
          (token_sha256,account_key,created_at,expires_at,revoked_at) VALUES(?,?,?,?,?)''',
          (advisor._sha('account-cookie'),account,app.now(),'2099-01-01T00:00:00Z',''))
        conn.execute('''INSERT INTO advisor_public_accounts
          (account_key,email,password_salt,password_hash,status,created_at,email_verified_at)
          VALUES(?,?,?,?,?,?,?)''',('SPA-ACCOUNT-OTHER','other@example.org','salt','hash',
          'Active',app.now(),app.now()))
        conn.execute('''INSERT INTO advisor_public_account_sessions
          (token_sha256,account_key,created_at,expires_at,revoked_at) VALUES(?,?,?,?,?)''',
          (advisor._sha('other-account-cookie'),'SPA-ACCOUNT-OTHER',app.now(),
           '2099-01-01T00:00:00Z',''))
        conn.execute('''INSERT INTO advisor_public_account_assessments
          (account_key,session_key,detailed_assessment_acknowledged,identifiable_retention_consent,acknowledged_at)
          VALUES(?,?,?,?,?)''',(account,session,1,1,app.now()))
        conn.execute('''INSERT INTO advisor_public_submissions
          (submission_key,session_key,organization_name,contact_name,contact_email,
           answer_snapshot_json,answer_snapshot_sha256,questionnaire_version,recommendation_version,
           consent_notice_version,retention_policy_version,secondary_deidentified_consent,
           result_json,status,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (submission,session,'Example Member','Example','member@example.org','{}','a'*64,
           'questions-v1','recommendation-v1','consent-v1','retention-v1',0,'{}','Awaiting Salus Review',app.now()))
        conn.execute('''INSERT INTO advisor_public_service_profiles
          (profile_key,submission_key,profile_version,profile_json,profile_sha256,
           package_recommendation_version,package_json,created_at) VALUES(?,?,?,?,?,?,?,?)''',
          ('SPA-PROFILE-TEST',submission,'profile-v1','{}','b'*64,'package-v1',
           json.dumps({'scope_receipt':{'receipt_id':receipt}}),app.now()))
        conn.execute('''INSERT INTO advisor_public_report_identity_revisions
          (revision_key,account_key,session_key,revision_no,protected_member_code_name,
           project_code_name,handling_profile,handling_status,created_by,created_at,content_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
          ('SPA-IDENTITY-TEST',account,session,1,'Member','Project','Commercial Confidential',
           'Approved','Member',app.now(),'c'*64))
        conn.execute('''INSERT INTO advisor_public_scope_receipt_snapshots
          (session_key,revision_no,package_version,template_version,item_id,content_sha256,
           content_size,created_at) VALUES(?,?,?,?,?,?,?,?)''',
          (session,1,'package-v1','receipt-v1','item-1','d'*64,12,app.now()))
        conn.commit();conn.close()
        advisor.read_member_pdf=lambda item_id,digest,size:b'verified-pdf'
        advisor.delete_member_pdf=lambda item_id:None
        prospect=TestClient(app.app,headers={'x-csrf-token':'csrf'},cookies={
          'salus_advisor_session':'session-cookie','salus_advisor_account':'account-cookie'})
        payload={'receipt_revision':1,'transfer_notice_version':advisor.PACKAGE_TRANSFER_NOTICE_VERSION,
                 'consent_to_package_handoff':True}
        app.ENVIRONMENT='production'
        assert prospect.get('/public/protection-advisor/package-handoff/notice').status_code==503
        assert prospect.post('/public/protection-advisor/package-handoff',json=payload).status_code==503
        app.ENVIRONMENT='development'
        notice=prospect.get('/public/protection-advisor/package-handoff/notice')
        assert notice.status_code==200 and notice.json()['version']==advisor.PACKAGE_TRANSFER_NOTICE_VERSION
        assert 'does not purchase an assessment' in notice.json()['notice']
        assert prospect.post('/public/protection-advisor/package-handoff',json={**payload,
          'consent_to_package_handoff':False}).status_code==422
        wrong=TestClient(app.app,headers={'x-csrf-token':'wrong'},cookies={
          'salus_advisor_session':'session-cookie','salus_advisor_account':'account-cookie'})
        assert wrong.post('/public/protection-advisor/package-handoff',json=payload).status_code==403
        other_account=TestClient(app.app,headers={'x-csrf-token':'csrf'},cookies={
          'salus_advisor_session':'session-cookie','salus_advisor_account':'other-account-cookie'})
        assert other_account.post('/public/protection-advisor/package-handoff',json=payload).status_code==403
        conn=app.db()
        conn.execute("UPDATE advisor_public_accounts SET email_verified_at='' WHERE account_key=?",(account,))
        conn.commit();conn.close()
        assert prospect.post('/public/protection-advisor/package-handoff',json=payload).status_code==409
        conn=app.db()
        conn.execute('UPDATE advisor_public_accounts SET email_verified_at=? WHERE account_key=?',
          (app.now(),account))
        conn.commit();conn.close()
        consent=prospect.post('/public/protection-advisor/package-handoff',json=payload)
        assert consent.status_code==200,consent.text
        handoff=consent.json()
        assert handoff['status'].startswith('Pending') and handoff['receipt_id']==receipt
        assert 'email' not in handoff
        assert prospect.post('/public/protection-advisor/package-handoff',json=payload).status_code==409
        conn=app.db()
        saved=conn.execute('SELECT * FROM advisor_package_handoffs WHERE handoff_key=?',
          (handoff['handoff_key'],)).fetchone()
        assert saved['claim_token_sha256']==advisor._sha(handoff['claim_code'])
        assert saved['tenant_id'] is None and saved['status']=='Pending'
        user_id=conn.execute('''INSERT INTO users
          (tenant_id,username,display_name,role,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)''',(1,'member-exec','Member Executive','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
          VALUES(?,?,?,?,?)''',(user_id,app._hash_token('member-cookie'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.execute('INSERT OR IGNORE INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)',
          (2,'Other tenant','other-tenant','Active',app.now()))
        other_id=conn.execute('''INSERT INTO users
          (tenant_id,username,display_name,role,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)''',(2,'other-exec','Other Executive','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
          VALUES(?,?,?,?,?)''',(other_id,app._hash_token('other-member-cookie'),
          '2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit();conn.close()
        app.AUTH_MODE='session'
        member=TestClient(app.app,cookies={'salus_session':'member-cookie'})
        claim={'claim_code':handoff['claim_code'],'confirm_requested_boundary':True}
        other_member=TestClient(app.app,cookies={'salus_session':'other-member-cookie'})
        assert other_member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==403
        conn=app.db()
        conn.execute('UPDATE advisor_package_handoffs SET claim_expires_at=? WHERE handoff_key=?',
          ('2000-01-01T00:00:00Z',handoff['handoff_key']))
        conn.commit();conn.close()
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==409
        conn=app.db()
        conn.execute('UPDATE advisor_package_handoffs SET claim_expires_at=? WHERE handoff_key=?',
          ('2099-01-01T00:00:00Z',handoff['handoff_key']))
        conn.commit();conn.close()
        app.ENVIRONMENT='production'
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==503
        app.ENVIRONMENT='development'
        claimed=member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim)
        assert claimed.status_code==200,claimed.text
        assert claimed.json()['status'].startswith('Awaiting Salus')
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==409
        withdrawal={'handoff_key':handoff['handoff_key']}
        assert other_account.post('/public/protection-advisor/package-handoff/withdraw',json=withdrawal).status_code==403
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM advisor_package_handoffs').fetchone()[0]==1
        conn.close()
        assert prospect.post('/public/protection-advisor/package-handoff/withdraw',json=withdrawal).json()=={'withdrawn':True}
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==409
        second=prospect.post('/public/protection-advisor/package-handoff',json=payload)
        assert second.status_code==200,second.text
        assert second.json()['handoff_key']!=handoff['handoff_key']
        deleted=prospect.post('/public/protection-advisor/delete')
        assert deleted.status_code==200,deleted.text
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM advisor_package_handoffs').fetchone()[0]==0
        assert conn.execute('SELECT COUNT(*) FROM advisor_public_submissions').fetchone()[0]==0
        conn.close()
    """)
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True,
                            capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
