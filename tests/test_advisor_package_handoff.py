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
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent("""
        import hashlib,json,os
        from fastapi.testclient import TestClient
        import app
        import public_protection_advisor as advisor

        assert app.system_mode()['package_handoff_candidate_available'] is False
        dashboard_js=open('static/app.js',encoding='utf-8').read()
        assert 'Connect a Protection Advisor receipt' in dashboard_js
        assert 'systemMode.package_handoff_candidate_available' in dashboard_js
        assert '/advisor-package-handoff' in dashboard_js

        page=advisor._page(include_shell=False)
        assert 'handoffEnabled="1"' in page and '__HANDOFF_ENABLED__' not in page
        assert 'Read the transfer notice' in page and 'Withdraw this handoff' in page
        assert 'id="handoffPanel"' in page and 'body.print-part2 main>*:not(#package)' in page
        os.environ['SALUS_ENV']='production'
        assert 'handoffEnabled="0"' in advisor._page(include_shell=False)
        os.environ['SALUS_ENV']='development'

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
        receipt_bytes=b'%PDF-1.4\\nreview-copy\\n%%EOF'
        receipt_digest=hashlib.sha256(receipt_bytes).hexdigest()
        profile_json=json.dumps({'covered_operation_tags':['Child care or early education'],
            'decision_authority':'Director','records_coordinator_role':'Office manager'},sort_keys=True)
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
          ('SPA-PROFILE-TEST',submission,'profile-v1',profile_json,advisor._sha(profile_json),'package-v1',
           json.dumps({'scope_receipt':{'receipt_id':receipt,
             'requested_boundary':'One operation','requested_location':'One site',
             'possible_path':'Level 1A Access','decision_owner':'Director',
             'records_coordinator':'Office manager'}}),app.now()))
        conn.execute('''INSERT INTO advisor_public_report_identity_revisions
          (revision_key,account_key,session_key,revision_no,protected_member_code_name,
           project_code_name,handling_profile,handling_status,created_by,created_at,content_sha256)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
          ('SPA-IDENTITY-TEST',account,session,1,'Member','Project','Commercial Confidential',
           'Approved','Member',app.now(),'c'*64))
        conn.execute('''INSERT INTO advisor_public_scope_receipt_snapshots
          (session_key,revision_no,package_version,template_version,item_id,content_sha256,
           content_size,created_at) VALUES(?,?,?,?,?,?,?,?)''',
          (session,1,'package-v1','receipt-v1','item-1',receipt_digest,len(receipt_bytes),app.now()))
        conn.commit();conn.close()
        def read_receipt(item_id,digest,size):
            assert item_id=='item-1' and digest==receipt_digest and size==len(receipt_bytes)
            return receipt_bytes
        advisor.read_member_pdf=read_receipt
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
        listed=prospect.get('/public/protection-advisor/package-handoffs')
        assert listed.status_code==200 and listed.json()['handoffs'][0]['handoff_key']==handoff['handoff_key']
        assert 'claim_code' not in listed.text
        assert other_account.get('/public/protection-advisor/package-handoffs').status_code==403
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
        reviewer_id=conn.execute('''INSERT INTO users
          (tenant_id,username,display_name,role,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)''',(1,'salus-reviewer','Salus Reviewer','Assessment Director',
          'Active',app.now(),app.now())).lastrowid
        conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
          VALUES(?,?,?,?,?)''',(reviewer_id,app._hash_token('reviewer-cookie'),
          '2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.execute('INSERT OR IGNORE INTO tenants(id,name,slug,status,created_at) VALUES(?,?,?,?,?)',
          (2,'Other tenant','other-tenant','Active',app.now()))
        other_id=conn.execute('''INSERT INTO users
          (tenant_id,username,display_name,role,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)''',(2,'other-exec','Other Executive','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
          VALUES(?,?,?,?,?)''',(other_id,app._hash_token('other-member-cookie'),
          '2099-01-01T00:00:00Z',app.now(),app.now()))
        other_reviewer_id=conn.execute('''INSERT INTO users
          (tenant_id,username,display_name,role,status,created_at,updated_at)
          VALUES(?,?,?,?,?,?,?)''',(2,'other-reviewer','Other Reviewer','Assessment Director',
          'Active',app.now(),app.now())).lastrowid
        conn.execute('''INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at)
          VALUES(?,?,?,?,?)''',(other_reviewer_id,app._hash_token('other-reviewer-cookie'),
          '2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit();conn.close()
        app.AUTH_MODE='session'
        assert app.system_mode()['package_handoff_candidate_available'] is True
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
        assert app.system_mode()['package_handoff_candidate_available'] is False
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==503
        app.ENVIRONMENT='development'
        claimed=member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim)
        assert claimed.status_code==200,claimed.text
        assert claimed.json()['status'].startswith('Awaiting Salus')
        assert member.post(f'/api/assessments/{assessment_id}/advisor-package-handoff',json=claim).status_code==409
        reviewer=TestClient(app.app,cookies={'salus_session':'reviewer-cookie'})
        other_reviewer=TestClient(app.app,cookies={'salus_session':'other-reviewer-cookie'})
        queue_url=f'/api/assessments/{assessment_id}/advisor-package-handoffs'
        assert member.get(queue_url).status_code==403
        assert other_reviewer.get(queue_url).status_code==403
        queue=reviewer.get(queue_url)
        assert queue.status_code==200 and len(queue.json()['handoffs'])==1
        assert queue.json()['handoffs'][0]['handoff_key']==handoff['handoff_key']
        assert 'claim_code' not in queue.text and 'member@example.org' not in queue.text
        review_url=f"/api/assessments/{assessment_id}/advisor-package-handoff/{handoff['handoff_key']}/review"
        packet_url=f"/api/assessments/{assessment_id}/advisor-package-handoff/{handoff['handoff_key']}/review-packet"
        receipt_url=f"/api/assessments/{assessment_id}/advisor-package-handoff/{handoff['handoff_key']}/receipt.pdf"
        assert member.get(packet_url).status_code==403
        packet=reviewer.get(packet_url)
        assert packet.status_code==200,packet.text
        assert packet.json()['prospect_receipt']['requested_boundary']=='One operation'
        assert packet.json()['prospect_receipt']['decision_role']=='Director'
        assert packet.json()['prospect_receipt']['records_coordinator']=='Office manager'
        assert packet.json()['consented_scope_signals']['covered_operation_tags']==['Child care or early education']
        assert packet.json()['consented_scope_signals']['profile_sha256']==advisor._sha(profile_json)
        assert packet.json()['member_request']['covered_operation']=='One operation'
        receipt_copy=reviewer.get(receipt_url)
        assert receipt_copy.status_code==200 and receipt_copy.content==receipt_bytes
        assert receipt_copy.headers['X-Content-SHA256']==receipt_digest
        def unavailable_receipt(item_id,digest,size):
            raise advisor.M365ReportError('unavailable')
        advisor.read_member_pdf=unavailable_receipt
        assert reviewer.get(receipt_url).status_code==503
        advisor.read_member_pdf=read_receipt
        review={'assessment_version':1,'organization_match_basis':'Confirmed organization from controlled records',
          'covered_boundary_basis':'Matched one named operation and exclusions',
          'decision_role_basis':'Confirmed Member role for quote preparation only',
          'confirm_exact_receipt':True}
        assert member.post(review_url,json=review).status_code==403
        assert reviewer.post(review_url,json={**review,'assessment_version':2}).status_code==409
        conn=app.db()
        conn.execute('UPDATE advisor_public_service_profiles SET profile_json=? WHERE submission_key=?',
          ('{"changed":true}',submission))
        conn.commit();conn.close()
        assert reviewer.get(packet_url).status_code==409
        assert reviewer.post(review_url,json=review).status_code==409
        conn=app.db()
        conn.execute('UPDATE advisor_public_service_profiles SET profile_json=? WHERE submission_key=?',
          (profile_json,submission))
        conn.commit();conn.close()
        assert reviewer.get(packet_url).status_code==200
        original_lock=app.lock_package_assessment
        def change_boundary_before_review_lock(db_conn,locked_assessment_id):
            race=app.db()
            race.execute('UPDATE assessments SET covered_operation=? WHERE id=?',
              ('Changed during review',locked_assessment_id))
            race.commit();race.close()
            return original_lock(db_conn,locked_assessment_id)
        app.lock_package_assessment=change_boundary_before_review_lock
        raced=reviewer.post(review_url,json=review)
        assert raced.status_code==409,raced.text
        app.lock_package_assessment=original_lock
        conn=app.db()
        assert conn.execute('SELECT status FROM advisor_package_handoffs WHERE handoff_key=?',
          (handoff['handoff_key'],)).fetchone()['status']=='Claimed'
        conn.execute('UPDATE assessments SET covered_operation=? WHERE id=?',
          ('One operation',assessment_id))
        conn.commit();conn.close()
        reviewed=reviewer.post(review_url,json=review)
        assert reviewed.status_code==200,reviewed.text
        assert reviewed.json()['status']=='Reviewed for quote preparation only'
        conn=app.db()
        saved=conn.execute('SELECT reviewed_assessment_scope_sha256 FROM advisor_package_handoffs WHERE handoff_key=?',
          (handoff['handoff_key'],)).fetchone()
        current=conn.execute('SELECT * FROM assessments WHERE id=?',(assessment_id,)).fetchone()
        assert saved['reviewed_assessment_scope_sha256']==app.assessment_scope_digest(current)
        conn.close()
        app.scan_bytes=lambda content,filename:{'ok':True,'status':'Clean'}
        agreement=b'%PDF-1.4\\n1 0 obj<</Type/Catalog>>endobj\\n%%EOF'
        agreement_sha=hashlib.sha256(agreement).hexdigest()
        uploaded=reviewer.post(f'/api/assessments/{assessment_id}/package-agreements',
          files={'file':('FictionalAgreement.pdf',agreement,'application/pdf')})
        assert uploaded.status_code==200,uploaded.text
        quote_payload=dict(assessment_version=1,level=1,band='A',variant='Access',
          covered_operation='One operation',exclusions='Other operations',
          scope_basis='One reviewed fictional decision unit',
          included_work='Four scoped Level 1 reports',member_inputs='Staged basic records',
          evidence_allowance='Named records and public sources',
          clarification_allowance='One remote clarification',
          field_specialist_terms='No field or specialist work included',
          payment_terms='Under separate written agreement',
          tax_treatment='As stated in the agreement',
          change_triggers='Additional work needs a written change',
          decision_owner='Director',source_receipt_id=receipt,fee_cents=150000,currency='USD',
          valid_until='2099-01-01',capacity_confirmed=True,
          access_eligibility_confirmed=True,access_eligibility_basis='One simple operation',
          agreement_artifact_id=uploaded.json()['id'],agreement_reference='FICTIONAL-AGREEMENT',
          agreement_sha256=agreement_sha,separate_services_excluded=True)
        quote_url=f'/api/assessments/{assessment_id}/package-quote'
        quoted=reviewer.post(quote_url,json=quote_payload)
        assert quoted.status_code==200,quoted.text
        assert quoted.json()['source_receipt_id']==receipt
        conn=app.db()
        linked=conn.execute('SELECT * FROM package_quote_advisor_receipt_links WHERE quote_id=?',
          (quoted.json()['id'],)).fetchone()
        assert linked['handoff_key']==handoff['handoff_key']
        assert linked['receipt_sha256']==receipt_digest
        assert linked['assessment_scope_sha256']==saved['reviewed_assessment_scope_sha256']
        conn.close()
        assert reviewer.post(review_url,json=review).status_code==409
        assert prospect.post('/public/protection-advisor/package-handoff',json=payload).status_code==409
        withdrawal={'handoff_key':handoff['handoff_key']}
        assert other_account.post('/public/protection-advisor/package-handoff/withdraw',json=withdrawal).status_code==403
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM advisor_package_handoffs').fetchone()[0]==1
        conn.close()
        assert prospect.post('/public/protection-advisor/package-handoff/withdraw',json=withdrawal).json()=={'withdrawn':True}
        assert reviewer.post(quote_url,json=quote_payload).status_code==409
        assert reviewer.get(queue_url).json()['handoffs']==[]
        assert reviewer.get(packet_url).status_code==404
        assert reviewer.get(receipt_url).status_code==404
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
