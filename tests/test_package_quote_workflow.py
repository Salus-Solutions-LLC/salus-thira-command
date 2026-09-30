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
        'PYTHONPATH': os.pathsep.join(filter(None, (os.getcwd(), env.get('PYTHONPATH', '')))),
    })
    program = textwrap.dedent('''
        import hashlib,io
        from docx import Document
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
                        {'organization':'Different organization'},
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
        conn.execute('UPDATE assessments SET organization=? WHERE id=?',('Other organization',assessment_id))
        conn.commit();conn.close()
        assert director.get(url).json()['status']=='Scope changed — new quote required'
        conn=app.db()
        conn.execute('UPDATE assessments SET organization=? WHERE id=?',('Example Member',assessment_id))
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
        report_url=f'/api/assessments/{assessment_id}/package-reports'
        def word_bytes(product):
            buf=io.BytesIO()
            document=Document()
            document.add_paragraph(f'Fictional {product} working draft')
            document.save(buf)
            return buf.getvalue()
        for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            content=word_bytes(product)
            draft=director.post(f'{report_url}/{product}/draft',data={'method_version':'approved-method-v1','template_version':'candidate-template-v1'},
                files={'file':(f'{product}.docx',content,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert draft.status_code==200,draft.text
            assert draft.json()['status']=='Draft' and draft.json()['version_no']==1
            assert draft.json()['display_title']==f'Example Member - {product} Level 1A Access'
            duplicate=director.post(f'{report_url}/{product}/draft',data={'method_version':'approved-method-v1','template_version':'candidate-template-v1'},
                files={'file':(f'{product}.docx',content,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert duplicate.status_code==200 and duplicate.json()['id']==draft.json()['id'],duplicate.text
            saved=director.get(f'/api/package-reports/{draft.json()["id"]}/draft.docx')
            assert saved.status_code==200 and saved.content==content
        revised=director.post(f'{report_url}/SalINTEL/draft',data={'method_version':'approved-method-v1','template_version':'candidate-template-v1'},
            files={'file':('SalINTEL revised.docx',word_bytes('SalINTEL revision'),'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert revised.status_code==200 and revised.json()['version_no']==2,revised.text
        report_rows=director.get(report_url).json()['reports']
        assert len(report_rows)==5
        intel_rows=[row for row in report_rows if row['product']=='SalINTEL']
        assert len({row['report_identity'] for row in intel_rows})==1
        assert len({row['display_title'] for row in intel_rows})==1
        assert intel_rows[1]['supersedes_id']==intel_rows[0]['id']
        current={product:max((row for row in report_rows if row['product']==product),
            key=lambda row:row['version_no']) for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA')}
        reconciliation_url=f'/api/package-reports/{current["SalCAPA"]["id"]}/source-reconciliation'
        sources={product:{'report_id':current[product]['id'],'content_sha256':current[product]['content_sha256'],
            'alignment':'Unresolved' if product=='SalINTEL' else 'Aligned',
            'explanation':'Fictional exact-version comparison; the open item needs qualified review.'}
            for product in ('SalINTEL','SalTHIRA','SalOPS')}
        comparison={'salcapa_sha256':current['SalCAPA']['content_sha256'],'sources':sources,
            'summary':'Fictional SalCAPA comparison records an unresolved SalINTEL item; no report is issued.'}
        assert director.post(reconciliation_url,json={**comparison,'sources':{'SalINTEL':sources['SalINTEL']}}).status_code==422
        stale_sources={**sources,'SalINTEL':{**sources['SalINTEL'],'report_id':intel_rows[0]['id'],
            'content_sha256':intel_rows[0]['content_sha256']}}
        assert director.post(reconciliation_url,json={**comparison,'sources':stale_sources}).status_code==409
        reconciled=director.post(reconciliation_url,json=comparison)
        assert reconciled.status_code==200 and reconciled.json()['comparison_status']=='Open',reconciled.text
        assert director.post(reconciliation_url,json=comparison).json()['idempotent'] is True
        assert len(director.get(reconciliation_url).json()['records'])==1
        preflight_url=f'/api/assessments/{assessment_id}/package-release-readiness'
        preflight=director.get(preflight_url)
        assert preflight.status_code==200 and preflight.json()['status']=='Blocked',preflight.text
        assert len(preflight.json()['reports'])==4
        assert any('SalCAPA: a source difference remains unresolved.' in item for item in preflight.json()['blockers'])
        assert any('recipient delivery proof' in item for item in preflight.json()['blockers'])
        conn=app.db()
        conn.execute('UPDATE package_report_reconciliations SET summary=? WHERE id=?',
            ('Altered comparison without a new immutable record.',reconciled.json()['id']))
        conn.commit();conn.close()
        assert any('comparison failed its integrity check' in item
            for item in director.get(preflight_url).json()['blockers'])
        conn=app.db()
        conn.execute('UPDATE package_report_reconciliations SET summary=? WHERE id=?',
            (comparison['summary'],reconciled.json()['id']))
        conn.commit();conn.close()
        qa_url=f'/api/package-reports/{revised.json()["id"]}/conformance'
        checks={key:{'status':'Pending','reason':'Exact-version evidence remains to be reviewed.'}
                for key in app.PACKAGE_REPORT_QA_KEYS}
        qa_payload={'content_sha256':revised.json()['content_sha256'],'checks':checks,
                    'summary':'All Charter items are recorded as pending until exact evidence is reviewed.'}
        assert director.post(qa_url,json={**qa_payload,'checks':{'accessibility':checks['accessibility']}}).status_code==422
        assert director.post(qa_url,json={**qa_payload,'content_sha256':'a'*64}).status_code==409
        qa=director.post(qa_url,json=qa_payload)
        assert qa.status_code==200 and qa.json()['matrix_status']=='Open',qa.text
        assert director.post(qa_url,json=qa_payload).json()['idempotent'] is True
        assert len(director.get(qa_url).json()['records'])==1
        conn=app.db()
        conn.execute('UPDATE package_report_conformance SET summary=? WHERE id=?',
            ('Altered Charter review without a new immutable record.',qa.json()['id']))
        conn.commit();conn.close()
        assert any('SalINTEL: the saved Charter check failed its integrity check.'==item
            for item in director.get(preflight_url).json()['blockers'])
        conn=app.db()
        conn.execute('UPDATE package_report_conformance SET summary=? WHERE id=?',
            (qa_payload['summary'],qa.json()['id']))
        conn.commit();conn.close()
        assert director.get(report_url).json()['reports'][-1]['status']=='Draft'
        retention_url=f'/api/package-reports/{revised.json()["id"]}/retention'
        assert director.patch(retention_url,json={'retention_until':'2030-01-01T00:00:00Z',
            'reason':'Fictional request to shorten retention must be stopped.'}).status_code==409
        held=director.patch(retention_url,json={'retention_until':'2099-01-01T00:00:00Z','legal_hold':True,
            'reason':'Fictional legal preservation and extended retention review.'})
        assert held.status_code==200 and held.json()['legal_hold'] is True,held.text
        assert director.patch(retention_url,json={'retention_until':'2098-01-01T00:00:00Z',
            'reason':'Fictional request to shorten extended retention.'}).status_code==409
        app.AUTH_MODE='session'
        conn=app.db()
        salus_user=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,created_at,updated_at) VALUES(1,?,?,?,?,?)',
            ('fictional-report-owner','Fictional report owner','Assessment Director',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (salus_user,app._hash_token('fictional-report-session'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit();conn.close()
        assigned_owner=TestClient(app.app,cookies={'salus_session':'fictional-report-session'})
        assert assigned_owner.get(report_url).status_code==403
        assert assigned_owner.get(f'/api/package-reports/{revised.json()["id"]}/draft.docx').status_code==403
        assert assigned_owner.get(qa_url).status_code==403
        conn=app.db()
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
                     (salus_user,assessment_id,app.now()))
        conn.commit();conn.close()
        assert assigned_owner.get(report_url).status_code==200
        assert assigned_owner.get(f'/api/package-reports/{revised.json()["id"]}/draft.docx').status_code==200
        assert assigned_owner.get(qa_url).status_code==200
        assert assigned_owner.get(reconciliation_url).status_code==200
        assert assigned_owner.get(preflight_url).status_code==200
        requested=member.get(intake_url)
        assert requested.status_code==200 and len(requested.json()['items'])==2,requested.text
        assert requested.json()['catalog']==[]
        assert member.get(report_url).status_code==403
        assert member.get(f'/api/package-reports/{revised.json()["id"]}/draft.docx').status_code==403
        assert member.get(qa_url).status_code==403
        assert member.get(reconciliation_url).status_code==403
        assert member.get(preflight_url).status_code==403
        assert member.patch(retention_url,json={'legal_hold':True,'reason':'No Member retention authority in this candidate.'}).status_code==403
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
        assert other_tenant.get(report_url).status_code==403
        assert other_tenant.get(reconciliation_url).status_code in (403,404)
        assert other_tenant.get(preflight_url).status_code==403
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
        assert conn.execute('SELECT COUNT(*) FROM package_product_report_versions').fetchone()[0]==5
        assert conn.execute('SELECT COUNT(*) FROM package_report_conformance').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_report_reconciliations').fetchone()[0]==1
        assert conn.execute('SELECT legal_hold FROM package_product_report_versions WHERE id=?',
            (revised.json()['id'],)).fetchone()[0]==1
        assert conn.execute('SELECT status FROM package_intake_requests WHERE id=?',(item_id,)).fetchone()[0]=='Not held'
        from portable_backup import collect_tenant_records, replace_tenant_records, validate_records
        records=collect_tenant_records(conn,1)
        assert len(records['package_quote_versions'])==1
        assert len(records['package_agreement_artifacts'])==1
        assert len(records['package_agreement_downloads'])==1
        assert len(records['package_acceptances'])==1
        assert len(records['package_intake_requests'])==2
        assert len(records['package_product_report_versions'])==5
        assert len(records['package_report_conformance'])==1
        assert len(records['package_report_reconciliations'])==1
        assert not validate_records(records,1)
        original_comparison=records['package_report_reconciliations'][0]['summary']
        records['package_report_reconciliations'][0]['summary']='Altered after the source comparison was created.'
        assert any('immutable source verification' in error for error in validate_records(records,1))
        records['package_report_reconciliations'][0]['summary']=original_comparison
        original_summary=records['package_report_conformance'][0]['summary']
        records['package_report_conformance'][0]['summary']='Altered after the conformance record was created.'
        assert any('immutable matrix verification' in error for error in validate_records(records,1))
        records['package_report_conformance'][0]['summary']=original_summary
        replace_tenant_records(conn,1,records)
        conn.commit()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_intake_requests').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_product_report_versions').fetchone()[0]==5
        assert conn.execute('SELECT COUNT(*) FROM package_report_conformance').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_report_reconciliations').fetchone()[0]==1
        assert conn.execute('SELECT legal_hold FROM package_product_report_versions WHERE id=?',
            (revised.json()['id'],)).fetchone()[0]==1
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
