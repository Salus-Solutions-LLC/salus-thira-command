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
        'SALUS_BACKUP_DIR': str(tmp_path / 'backups'),
        'SALUS_SEED_DEMO': '0',
        'SALUS_AUTH_MODE': 'prototype',
        'SALUS_PACKAGE_COMMERCIAL_WORKFLOW_ENABLED': '1',
        'PYTHONPATH': os.getcwd(),
    })
    program = textwrap.dedent('''
        import hashlib
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
        app.scan_bytes=lambda content,filename:{'ok':True,'status':'Clean'}
        pdf=b'%PDF-1.4\\n1 0 obj<</Type/Catalog>>endobj\\n%%EOF'
        agreement_digest=hashlib.sha256(pdf).hexdigest()
        upload=director.post(f'/api/assessments/{assessment_id}/package-agreements',files={'file':('Agreement.pdf',pdf,'application/pdf')})
        assert upload.status_code==200, upload.text
        agreement_id=upload.json()['id']
        repeated=director.post(f'/api/assessments/{assessment_id}/package-agreements',files={'file':('Agreement.pdf',pdf,'application/pdf')})
        assert repeated.status_code==200 and repeated.json()['id']==agreement_id
        quote = dict(assessment_version=1,level=1,band='A',variant='Access',
            covered_operation='One named operation',exclusions='Other sites and functions',
            scope_basis='Reviewed one decision unit and basic records',
            included_work='Bounded source review, capability and option assessment',
            member_inputs='Short staged records packet and one decision owner',
            evidence_allowance='Named basic records and official sources for the agreed boundary',
            clarification_allowance='One remote clarification',
            field_specialist_terms='No field visit or specialist certification included',
            payment_terms='Payment under signed agreement',tax_treatment='Tax under signed agreement',
            change_triggers='Added site, different operation or requested field work requires written change',
            decision_owner='Director',
            source_receipt_id='',fee_cents=150000,currency='USD',
            valid_until='2099-01-01',capacity_confirmed=True,
            access_eligibility_confirmed=True,access_eligibility_basis='One simple operation',
            agreement_artifact_id=agreement_id,agreement_reference='AGREEMENT-1',agreement_sha256=agreement_digest,
            separate_services_excluded=True)
        url=f'/api/assessments/{assessment_id}/package-quote'
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED=False
        assert director.post(url,json=quote).status_code==503
        app.PACKAGE_COMMERCIAL_WORKFLOW_ENABLED=True
        app.ENVIRONMENT='production'
        assert director.post(url,json=quote).status_code==503
        app.ENVIRONMENT='development'
        unverified=director.post(url,json={**quote,'source_receipt_id':'SPA-EXAMPLE'})
        assert unverified.status_code==409, unverified.text
        bad=director.post(url,json={**quote,'access_eligibility_confirmed':False})
        assert bad.status_code == 422, bad.text
        # A concurrent boundary edit after the initial validation must stop issue.
        original_read=app.storage.get_bytes
        def change_scope_during_agreement_read(name):
            content=original_read(name)
            conn=app.db()
            conn.execute('UPDATE assessments SET covered_operation=? WHERE id=?',('Changed while quoting',assessment_id))
            conn.commit();conn.close()
            return content
        app.storage.get_bytes=change_scope_during_agreement_read
        raced=director.post(url,json=quote)
        assert raced.status_code==409, raced.text
        app.storage.get_bytes=original_read
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==0
        conn.execute('UPDATE assessments SET covered_operation=? WHERE id=?',('One named operation',assessment_id))
        conn.commit();conn.close()
        response=director.post(url,json=quote)
        assert response.status_code == 200, response.text
        issued=response.json()
        assert issued['fee_cents']==150000 and issued['version_no']==1
        assert len(issued['assessment_scope_sha256'])==64
        assert director.get(url).json()['status']=='Quoted'
        legacy_content={key:issued[key] for key in app.PackageQuoteIn.model_fields}
        for key in ('capacity_confirmed','access_eligibility_confirmed','separate_services_excluded'):
            legacy_content[key]=bool(legacy_content[key])
        legacy_content.update(assessment_id=assessment_id,tenant_id=1,version_no=1)
        legacy_digest=app.quote_digest(legacy_content)
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET assessment_scope_sha256=?,content_sha256=? WHERE id=?',('',legacy_digest,issued['id']))
        conn.commit();conn.close()
        assert director.get(url).json()['status']=='Scope proof missing — new quote required'
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET assessment_scope_sha256=?,content_sha256=? WHERE id=?',
                     (issued['assessment_scope_sha256'],issued['content_sha256'],issued['id']))
        conn.commit();conn.close()
        # A quoted boundary cannot be overwritten by the ordinary assessment editor.
        for changed in ({'covered_operation':'Different operation'},
                        {'exclusions':'Different exclusions'},
                        {'purpose':'Different purpose'}):
            blocked=director.put(f'/api/assessments/{assessment_id}',json=changed)
            assert blocked.status_code==409, blocked.text
        # Earlier data may contain a same-version drift; read and acceptance must fail closed.
        conn=app.db()
        conn.execute('UPDATE assessments SET covered_operation=? WHERE id=?',('Different operation',assessment_id))
        conn.commit();conn.close()
        assert director.get(url).json()['status']=='Scope changed — new quote required'
        conn=app.db()
        conn.execute('UPDATE assessments SET covered_operation=? WHERE id=?',('One named operation',assessment_id))
        conn.commit();conn.close()
        conn=app.db()
        conn.execute('UPDATE assessments SET purpose=? WHERE id=?',('Changed purpose without version bump',assessment_id))
        conn.commit();conn.close()
        assert director.get(url).json()['status']=='Scope changed — new quote required'
        conn=app.db()
        conn.execute('UPDATE assessments SET purpose=? WHERE id=?',('',assessment_id))
        conn.commit();conn.close()
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET source_receipt_id=? WHERE id=?',('SPA-EXAMPLE',issued['id']))
        conn.commit(); conn.close()
        assert director.get(url).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET source_receipt_id=? WHERE id=?',('',issued['id']))
        conn.commit(); conn.close()
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET fee_cents=? WHERE id=?',(150001,issued['id']))
        conn.commit(); conn.close()
        assert director.get(url).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_quote_versions SET fee_cents=? WHERE id=?',(150000,issued['id']))
        conn.commit(); conn.close()
        acceptance=dict(quote_id=issued['id'],quote_sha256=issued['content_sha256'],
            agreement_sha256=agreement_digest,member_authority_basis='Authorized Member executive',
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
        intake_url=f'/api/assessments/{assessment_id}/package-intake'
        assert member.get(intake_url).status_code==409
        conn=app.db()
        conn.execute('UPDATE assessments SET purpose=? WHERE id=?',('Different decision purpose',assessment_id))
        conn.commit();conn.close()
        purpose_drift=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert purpose_drift.status_code==409 and 'superseded' in purpose_drift.text, purpose_drift.text
        conn=app.db()
        conn.execute('UPDATE assessments SET purpose=? WHERE id=?',('',assessment_id))
        conn.commit();conn.close()
        original_scope_read=app.assessment_row_for_request
        def change_scope_after_access_check(request, aid):
            row=original_scope_read(request,aid)
            app.assessment_row_for_request=original_scope_read
            conn=app.db()
            conn.execute('UPDATE assessments SET exclusions=? WHERE id=?',('Changed before acceptance lock',assessment_id))
            conn.commit();conn.close()
            return row
        app.assessment_row_for_request=change_scope_after_access_check
        assert member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance).status_code==409
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==0
        conn.execute('UPDATE assessments SET exclusions=? WHERE id=?',('Other sites and functions',assessment_id))
        conn.commit();conn.close()
        conn=app.db()
        conn.execute('UPDATE assessments SET exclusions=? WHERE id=?',('Different exclusions',assessment_id))
        conn.commit();conn.close()
        assert member.get(url).json()['status']=='Scope changed — new quote required'
        assert member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance).status_code==409
        conn=app.db()
        conn.execute('UPDATE assessments SET exclusions=? WHERE id=?',('Other sites and functions',assessment_id))
        conn.commit();conn.close()
        missing_delivery=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert missing_delivery.status_code==409, missing_delivery.text
        conn=app.db()
        stored=conn.execute('SELECT stored_name FROM package_agreement_artifacts WHERE id=?',(agreement_id,)).fetchone()['stored_name']
        conn.close()
        app.storage.put_bytes(stored,b'%PDF-corrupted')
        assert member.get(f'/api/package-agreements/{agreement_id}/download').status_code==409
        app.storage.put_bytes(stored,pdf)
        agreement_copy=member.get(f'/api/package-agreements/{agreement_id}/download')
        assert agreement_copy.status_code==200 and agreement_copy.content==pdf
        assert agreement_copy.headers['X-Content-SHA256']==agreement_digest
        stale=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json={**acceptance,'quote_sha256':'b'*64})
        assert stale.status_code==409, stale.text
        accepted=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert accepted.status_code==200, accepted.text
        assert accepted.json()['status']=='Authorized'
        retry=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert retry.status_code==200 and retry.json()['idempotent'] is True, retry.text
        assert member.get(intake_url).json()['items']==[]
        assert member.post(intake_url,json={'item_keys':['GOV'],'request_reason':'Needed to confirm authority'}).status_code==403
        app.AUTH_MODE='prototype'
        selected=director.post(intake_url,json={'item_keys':['GOV','FUN'],'request_reason':'Needed to confirm authority and essential work'})
        assert selected.status_code==200,selected.text
        repeated=director.post(intake_url,json={'item_keys':['GOV','FUN'],'request_reason':'Needed to confirm authority and essential work'})
        assert repeated.status_code==200,repeated.text
        app.AUTH_MODE='session'
        requested=member.get(intake_url)
        assert requested.status_code==200 and len(requested.json()['items'])==2,requested.text
        assert requested.json()['catalog']==[]
        assert 'response_user_id' not in requested.json()['items'][0]
        item_id=requested.json()['items'][0]['id']
        response=member.patch(f'{intake_url}/{item_id}',json={'status':'Not held'})
        assert response.status_code==200 and response.json()['status']=='Not held',response.text
        assert member.get(intake_url).json()['items'][0]['status']=='Not held'
        assert member.get(url).json()['status']=='Authorized'
        assert director.post(url,json=quote).status_code==401
        app.AUTH_MODE='prototype'
        assert director.post(url,json=quote).status_code==409
        other_tenant=TestClient(app.app,headers={'X-Salus-Role':'Assessment Director','X-Salus-Tenant':'2'})
        assert other_tenant.get(url).status_code==403
        assert other_tenant.get(intake_url).status_code==403
        admin=TestClient(app.app,headers={'X-Salus-Role':'System Administrator'})
        backup=admin.post('/api/admin/backups')
        assert backup.status_code==200, backup.text
        validation=admin.post(f"/api/admin/backups/{backup.json()['id']}/dr-validate")
        assert validation.status_code==200 and validation.json()['ok'], validation.text
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_agreement_artifacts').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_agreement_downloads').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_intake_requests').fetchone()[0]==2
        assert conn.execute('SELECT status FROM package_intake_requests WHERE id=?',(item_id,)).fetchone()[0]=='Not held'
        from portable_backup import collect_tenant_records, replace_tenant_records, validate_records
        records=collect_tenant_records(conn,1)
        assert len(records['package_quote_versions'])==1
        assert len(records['package_agreement_artifacts'])==1
        assert len(records['package_agreement_downloads'])==1
        assert len(records['package_acceptances'])==1
        assert len(records['package_intake_requests'])==2
        assert not validate_records(records,1)
        replace_tenant_records(conn,1,records)
        conn.commit()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_intake_requests').fetchone()[0]==2
        assert conn.execute('SELECT status FROM package_intake_requests WHERE id=?',(item_id,)).fetchone()[0]=='Not held'
        conn.close()
        # A historical Executive snapshot cannot stand in for four issued package reports.
        conn=app.db()
        snapshot='{}'
        conn.execute("""INSERT INTO report_versions
          (tenant_id,assessment_id,assessment_version,report_type,status,snapshot_json,
           snapshot_sha256,created_by,created_at,released_by,released_at)
          VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
          (1,assessment_id,1,'Executive','Released',snapshot,
           hashlib.sha256(snapshot.encode()).hexdigest(),'Fixture',app.now(),'Fixture',app.now()))
        conn.commit();conn.close()
        next_scope=director.post('/api/assessments',json={
            'name':'Focused follow-up','organization':'Example Member',
            'covered_operation':'One named operation','exclusions':'Other sites and functions',
            'requested_package_level':2,'requested_scope_band':'A'})
        assert next_scope.status_code==200,next_scope.text
        next_id=next_scope.json()['id']
        next_quote={**quote,'level':2,'variant':'','fee_cents':500000,
                    'access_eligibility_confirmed':False,'access_eligibility_basis':''}
        blocked=director.post(f'/api/assessments/{next_id}/package-quote',json=next_quote)
        assert blocked.status_code==409 and 'qualified issued predecessor' in blocked.text
    ''')
    result = subprocess.run([sys.executable, '-c', program], env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
