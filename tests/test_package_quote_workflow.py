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
        import hashlib,io,json,zipfile
        from docx import Document
        from reportlab.pdfgen import canvas
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
        original_scan=app.scan_bytes
        app.scan_bytes=lambda *_args: (_ for _ in ()).throw(AssertionError('A known clean agreement must not be rescanned'))
        repeated=director.post(f'/api/assessments/{assessment_id}/package-agreements',files={'file':('Agreement.pdf',pdf,'application/pdf')})
        assert repeated.status_code==200 and repeated.json()['id']==agreement_id
        app.scan_bytes=original_scan
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
        conn=app.db()
        conn.execute('UPDATE package_agreement_artifacts SET scan_status=? WHERE id=?',('Pending',agreement_id))
        conn.commit();conn.close()
        pending_quote=director.post(url,json=quote)
        assert pending_quote.status_code==409 and 'security check' in pending_quote.text,pending_quote.text
        pending_retry=director.post(f'/api/assessments/{assessment_id}/package-agreements',
            files={'file':('Agreement.pdf',pdf,'application/pdf')})
        assert pending_retry.status_code==409,pending_retry.text
        conn=app.db()
        conn.execute('UPDATE package_agreement_artifacts SET scan_status=? WHERE id=?',('Clean',agreement_id))
        conn.commit();conn.close()
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
        legacy_content={key:issued[key] for key in app.PackageQuoteIn.model_fields
            if key!='predecessor_qualification_id'}
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
        reviewer_id=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'salus-reviewer','Salus Reviewer','Assessment Director','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (reviewer_id,app._hash_token('reviewer-cookie'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        other_member_id=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'other-exec','Other Member Executive','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (other_member_id,app._hash_token('other-cookie'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit(); conn.close()
        app.AUTH_MODE='session'
        member=TestClient(app.app,cookies={'salus_session':'test-cookie'})
        reviewer=TestClient(app.app,cookies={'salus_session':'reviewer-cookie'})
        other_member=TestClient(app.app,cookies={'salus_session':'other-cookie'})
        review_url=f'/api/assessments/{assessment_id}/package-member-authority'
        authority_review={'quote_id':issued['id'],'member_user_id':user_id,
            'authority_basis':'Reviewed board delegation for this agreement',
            'evidence_reference':'BOARD-AUTHORITY-RECORD-1','confirm_external_authority':True}
        without_review=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert without_review.status_code==409 and 'verify this Member signer' in without_review.text,without_review.text
        assert member.get(url).json()=={'status':'Awaiting Salus signer review'}
        assert other_member.get(url).json()=={'status':'Awaiting Salus signer review'}
        assert director.post(review_url,json=authority_review).status_code==401
        bad_signer=reviewer.post(review_url,json={**authority_review,'member_user_id':reviewer_id})
        assert bad_signer.status_code==409,bad_signer.text
        reviewed=reviewer.post(review_url,json=authority_review)
        assert reviewed.status_code==200 and reviewed.json()['idempotent'] is False,reviewed.text
        repeated_review=reviewer.post(review_url,json=authority_review)
        assert repeated_review.status_code==200 and repeated_review.json()['idempotent'] is True,repeated_review.text
        assert member.get(url).json()['status']=='Quoted'
        assert other_member.get(url).status_code==403
        assert other_member.get(f'/api/package-agreements/{agreement_id}/download').status_code==409
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
        conn.execute('UPDATE package_agreement_artifacts SET scan_status=? WHERE id=?',('Pending',agreement_id))
        conn.commit();conn.close()
        pending_download=member.get(f'/api/package-agreements/{agreement_id}/download')
        assert pending_download.status_code==409 and 'security check' in pending_download.text,pending_download.text
        pending_acceptance=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert pending_acceptance.status_code==409 and 'security check' in pending_acceptance.text,pending_acceptance.text
        conn=app.db()
        conn.execute('UPDATE package_agreement_artifacts SET scan_status=? WHERE id=?',('Clean',agreement_id))
        conn.commit();conn.close()
        conn=app.db()
        stored=conn.execute('SELECT stored_name FROM package_agreement_artifacts WHERE id=?',(agreement_id,)).fetchone()['stored_name']
        conn.close()
        app.storage.put_bytes(stored,b'%PDF-corrupted')
        assert member.get(f'/api/package-agreements/{agreement_id}/download').status_code==409
        app.storage.put_bytes(stored,pdf)
        agreement_copy=member.get(f'/api/package-agreements/{agreement_id}/download')
        assert agreement_copy.status_code==200 and agreement_copy.content==pdf
        assert agreement_copy.headers['X-Content-SHA256']==agreement_digest
        conn=app.db()
        conn.execute('UPDATE package_member_authority_reviews SET authority_basis=? WHERE quote_id=?',
            ('Changed after review',issued['id']))
        conn.commit();conn.close()
        altered_review=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert altered_review.status_code==409 and 'verify this Member signer' in altered_review.text,altered_review.text
        conn=app.db()
        conn.execute('UPDATE package_member_authority_reviews SET authority_basis=? WHERE quote_id=?',
            (authority_review['authority_basis'],issued['id']))
        conn.commit();conn.close()
        stale=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json={**acceptance,'quote_sha256':'b'*64})
        assert stale.status_code==409, stale.text
        accepted=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert accepted.status_code==200, accepted.text
        assert accepted.json()['status']=='Authorized'
        retry=member.post(f'/api/assessments/{assessment_id}/package-acceptance',json=acceptance)
        assert retry.status_code==200 and retry.json()['idempotent'] is True, retry.text
        changed_basis=member.post(f'/api/assessments/{assessment_id}/package-acceptance',
            json={**acceptance,'member_authority_basis':'Different claimed authority'})
        assert changed_basis.status_code==409,changed_basis.text
        conn=app.db()
        conn.execute('UPDATE package_member_authority_reviews SET member_user_id=? WHERE quote_id=?',
            (reviewer_id,issued['id']))
        conn.commit();conn.close()
        assert member.get(url).status_code==409
        assert member.get(intake_url).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_member_authority_reviews SET member_user_id=? WHERE quote_id=?',
            (user_id,issued['id']))
        conn.commit();conn.close()
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
        qa_archive_url=f'/api/package-reports/{revised.json()["id"]}/qa-evidence'
        pdf_buffer=io.BytesIO()
        pdf_canvas=canvas.Canvas(pdf_buffer)
        pdf_canvas.drawString(60,40,'page 1 of 3')
        pdf_canvas.showPage()
        pdf_canvas.showPage()
        pdf_canvas.drawString(60,40,'page 3 of 3')
        pdf_canvas.save()
        rendered_pdf=pdf_buffer.getvalue()
        page_log=[{'page':number,'checked_full_size':False,'note':'Fictional review remains pending.'}
            for number in range(1,4)]
        manifest={'report_sha256':revised.json()['content_sha256'],
            'pdf_sha256':hashlib.sha256(rendered_pdf).hexdigest(),
            'renderer':'Fictional ReportLab renderer','pages':page_log,'native_word':'Pending',
            'accessibility':'Pending','parity':'Pending','notes':'Candidate archive; no qualified review.'}
        def qa_zip(metadata):
            out=io.BytesIO()
            with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('manifest.json',json.dumps(metadata))
                archive.writestr('rendered.pdf',rendered_pdf)
            return out.getvalue()
        assert director.post(qa_archive_url,files={'file':('qa.zip',qa_zip({**manifest,
            'report_sha256':'0'*64}),'application/zip')}).status_code==422
        qa_bytes=qa_zip(manifest)
        submitted=director.post(qa_archive_url,files={'file':('qa.zip',qa_bytes,'application/zip')})
        assert submitted.status_code==200 and submitted.json()['status']=='Submitted',submitted.text
        assert any('SalINTEL: rendered page, accessibility or format parity review is pending.'==item
            for item in director.get(preflight_url).json()['blockers'])
        assert director.post(qa_archive_url,files={'file':('qa.zip',qa_bytes,'application/zip')}).json()['idempotent'] is True
        assert len(director.get(qa_archive_url).json()['records'])==1
        downloaded=director.get(f'/api/package-report-qa/{submitted.json()["id"]}/archive.zip')
        assert downloaded.status_code==200 and downloaded.content==qa_bytes
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
        assert assigned_owner.get(qa_archive_url).status_code==403
        conn=app.db()
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
                     (salus_user,assessment_id,app.now()))
        conn.commit();conn.close()
        assert assigned_owner.get(report_url).status_code==200
        assert assigned_owner.get(f'/api/package-reports/{revised.json()["id"]}/draft.docx').status_code==200
        assert assigned_owner.get(qa_url).status_code==200
        assert assigned_owner.get(qa_archive_url).status_code==200
        review_url=f'/api/package-reports/{revised.json()["id"]}/qa-reviews'
        complete_manifest={**manifest,'pages':[
            {'page':number,'checked_full_size':True,'note':'Fictional full-size check recorded.'}
            for number in range(1,4)],'native_word':'Checked','accessibility':'Checked',
            'parity':'Checked','notes':'Fictional completed QA candidate; independent decision remains separate.'}
        reviewed_archive=assigned_owner.post(qa_archive_url,files={'file':(
            'qa-complete.zip',qa_zip(complete_manifest),'application/zip')})
        assert reviewed_archive.status_code==200,reviewed_archive.text
        review_payload={'evidence_id':reviewed_archive.json()['id'],'decision':'Reviewed',
            'checks':{key:True for key in app.PACKAGE_REPORT_REVIEW_KEYS},
            'qualification_basis':'Fictional reviewer qualification record for the test only.',
            'review_note':'Fictional exact-version review of every page and offered output.'}
        assert assigned_owner.post(review_url,json=review_payload).status_code==409
        conn=app.db()
        reviewer_id=conn.execute('INSERT INTO users(tenant_id,username,display_name,role,created_at,updated_at) VALUES(1,?,?,?,?,?)',
            ('fictional-independent-reviewer','Fictional independent reviewer','Assessment Director',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions(user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (reviewer_id,app._hash_token('fictional-review-session'),'2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
            (reviewer_id,assessment_id,app.now()))
        conn.commit();conn.close()
        reviewer=TestClient(app.app,cookies={'salus_session':'fictional-review-session'})
        assert reviewer.post(review_url,json={**review_payload,
            'evidence_id':submitted.json()['id']}).status_code==409
        assert reviewer.post(review_url,json={**review_payload,
            'checks':{**review_payload['checks'],'accessibility':False}}).status_code==422
        review=reviewer.post(review_url,json=review_payload)
        assert review.status_code==200 and review.json()['decision']=='Reviewed',review.text
        assert reviewer.post(review_url,json=review_payload).json()['idempotent'] is True
        assert len(reviewer.get(review_url).json()['records'])==1
        conn=app.db()
        conn.execute('UPDATE package_report_qa_reviews SET review_note=? WHERE id=?',
            ('Altered QA review without a new immutable record.',review.json()['id']))
        conn.commit();conn.close()
        assert any('SalINTEL: the independent QA review failed its integrity check.'==item
            for item in reviewer.get(preflight_url).json()['blockers'])
        conn=app.db()
        conn.execute('UPDATE package_report_qa_reviews SET review_note=? WHERE id=?',
            (review_payload['review_note'],review.json()['id']))
        conn.commit();conn.close()
        assert assigned_owner.get(reconciliation_url).status_code==200
        assert assigned_owner.get(preflight_url).status_code==200
        issue_url=f'/api/assessments/{assessment_id}/package-issues'
        issue_payload={'report_ids':{product:current[product]['id'] for product in current},
            'recipient_user_id':user_id,
            'issue_basis':'Fictional qualified issue basis for the exact four reports and named recipient.',
            'confirm_qualified_release':True}
        assert reviewer.post(issue_url,json=issue_payload).status_code==409
        complete_checks={key:{'status':'Met','reason':'Fictional exact-version review evidence for this test.'}
            for key in app.PACKAGE_REPORT_QA_KEYS}
        for product,row in current.items():
            matrix_url=f'/api/package-reports/{row["id"]}/conformance'
            matrix=reviewer.post(matrix_url,json={'content_sha256':row['content_sha256'],
                'checks':complete_checks,'summary':'Fictional complete Charter review for issue-path testing.'})
            assert matrix.status_code==200,matrix.text
            if product=='SalINTEL': continue
            other_manifest={**complete_manifest,'report_sha256':row['content_sha256']}
            other_qa_url=f'/api/package-reports/{row["id"]}/qa-evidence'
            other_archive=assigned_owner.post(other_qa_url,files={'file':(
                f'{product}-qa.zip',qa_zip(other_manifest),'application/zip')})
            assert other_archive.status_code==200,other_archive.text
            other_review=reviewer.post(f'/api/package-reports/{row["id"]}/qa-reviews',
                json={**review_payload,'evidence_id':other_archive.json()['id']})
            assert other_review.status_code==200,other_review.text
        aligned={product:{**value,'alignment':'Aligned'} for product,value in sources.items()}
        compared=reviewer.post(reconciliation_url,json={**comparison,'sources':aligned,
            'summary':'Fictional complete source comparison for the exact four-report issue path.'})
        assert compared.status_code==200 and compared.json()['comparison_status']=='Compared',compared.text
        assert reviewer.get(preflight_url).json()['technical_blockers']==[]
        issued_packet=reviewer.post(issue_url,json=issue_payload)
        assert issued_packet.status_code==200 and issued_packet.json()['status']=='Issued',issued_packet.text
        assert reviewer.post(issue_url,json=issue_payload).json()['idempotent'] is True
        assert assigned_owner.get(issue_url).status_code==403
        assert member.get(issue_url).json()['issues'][0]['id']==issued_packet.json()['id']
        doc_delivery=member.get(f'/api/package-issues/{issued_packet.json()["id"]}/reports/SalINTEL.docx')
        pdf_delivery=member.get(f'/api/package-issues/{issued_packet.json()["id"]}/reports/SalINTEL.pdf')
        assert doc_delivery.status_code==200 and pdf_delivery.status_code==200
        assert hashlib.sha256(doc_delivery.content).hexdigest()==revised.json()['content_sha256']
        assert hashlib.sha256(pdf_delivery.content).hexdigest()==hashlib.sha256(rendered_pdf).hexdigest()
        acknowledgment_url=f'/api/package-issues/{issued_packet.json()["id"]}/acknowledgment'
        acknowledgment_payload={'issue_sha256':issued_packet.json()['record_sha256'],
            'confirm_received':True,'confirm_reviewed_limitations':True,
            'acknowledgment_note':'Fictional recipient confirms receipt and review of limitations.',
            'idempotency_key':'fictional-receipt-001'}
        assert member.post(acknowledgment_url,json=acknowledgment_payload).status_code==409
        predecessor_url=f'/api/assessments/{assessment_id}/package-predecessor-qualifications'
        predecessor_payload={'issue_sha256':issued_packet.json()['record_sha256'],
            'acknowledgment_id':1,
            'qualification_basis':'Fictional independent review of exact Level 1 issue and successor boundary.',
            'limitations_disposition':'Fictional open limitations recorded for review before any Level 2 quote.',
            'confirm_independent_review':True}
        assert assigned_owner.post(predecessor_url,json=predecessor_payload).status_code==409
        for product in ('SalTHIRA','SalOPS','SalCAPA'):
            delivered=member.get(f'/api/package-issues/{issued_packet.json()["id"]}/reports/{product}.docx')
            assert delivered.status_code==200,delivered.text
        acknowledged=member.post(acknowledgment_url,json=acknowledgment_payload)
        assert acknowledged.status_code==200 and acknowledged.json()['status']=='Acknowledged',acknowledged.text
        predecessor_payload['acknowledgment_id']=acknowledged.json()['id']
        assert reviewer.post(predecessor_url,json=predecessor_payload).status_code==403
        qualified=assigned_owner.post(predecessor_url,json=predecessor_payload)
        assert qualified.status_code==200 and qualified.json()['status']=='Qualified',qualified.text
        assert assigned_owner.post(predecessor_url,json=predecessor_payload).json()['idempotent'] is True
        assert assigned_owner.post(predecessor_url,json={**predecessor_payload,
            'limitations_disposition':'Fictional changed limits cannot overwrite a qualification record.'}).status_code==409
        next_assessment=assigned_owner.post('/api/assessments',json={
            'name':'Focused same-boundary review','organization':'Example Member',
            'covered_operation':'One named operation','exclusions':'Other sites and functions',
            'requested_package_level':2,'requested_scope_band':'A',
            'requested_access_variant':''})
        assert next_assessment.status_code==200,next_assessment.text
        next_assessment_id=next_assessment.json()['id']
        conn=app.db()
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
            (salus_user,next_assessment_id,app.now()))
        conn.commit();conn.close()
        next_agreement=assigned_owner.post(f'/api/assessments/{next_assessment_id}/package-agreements',
            files={'file':('Focused-Agreement.pdf',pdf,'application/pdf')})
        assert next_agreement.status_code==200,next_agreement.text
        next_quote={**quote,'level':2,'band':'A','variant':'','fee_cents':850000,
            'access_eligibility_confirmed':False,'access_eligibility_basis':'',
            'agreement_artifact_id':next_agreement.json()['id'],
            'agreement_reference':'FOCUSED-AGREEMENT-1',
            'predecessor_qualification_id':qualified.json()['id']}
        next_quote_url=f'/api/assessments/{next_assessment_id}/package-quote'
        assert assigned_owner.post(next_quote_url,json={**next_quote,
            'predecessor_qualification_id':0}).status_code==409
        focused=assigned_owner.post(next_quote_url,json=next_quote)
        assert focused.status_code==200 and focused.json()['level']==2,focused.text
        focused_review=assigned_owner.post(
            f'/api/assessments/{next_assessment_id}/package-member-authority',
            json={**authority_review,'quote_id':focused.json()['id']})
        assert focused_review.status_code==200,focused_review.text
        assert assigned_owner.get(next_quote_url).json()['status']=='Quoted'
        next_agreement_download=member.get(
            f'/api/package-agreements/{next_agreement.json()["id"]}/download')
        assert next_agreement_download.status_code==200,next_agreement_download.text
        next_acceptance={**acceptance,'quote_id':focused.json()['id'],
            'quote_sha256':focused.json()['content_sha256'],
            'idempotency_key':'member-acceptance-level2'}
        conn=app.db()
        conn.execute('UPDATE package_predecessor_qualifications SET qualification_basis=? WHERE id=?',
            ('Altered predecessor qualification after quote issue.',qualified.json()['id']))
        conn.commit();conn.close()
        assert member.post(f'/api/assessments/{next_assessment_id}/package-acceptance',
            json=next_acceptance).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_predecessor_qualifications SET qualification_basis=? WHERE id=?',
            (predecessor_payload['qualification_basis'],qualified.json()['id']))
        conn.commit();conn.close()
        accepted_level2=member.post(f'/api/assessments/{next_assessment_id}/package-acceptance',
            json=next_acceptance)
        assert accepted_level2.status_code==200 and accepted_level2.json()['status']=='Authorized',accepted_level2.text
        assert member.get(f'/api/assessments/{next_assessment_id}/package-intake').status_code==200
        conn=app.db()
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
            (reviewer_id,next_assessment_id,app.now()))
        conn.commit();conn.close()
        level2_report_url=f'/api/assessments/{next_assessment_id}/package-reports'
        level2_reports={}
        for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            draft=assigned_owner.post(f'{level2_report_url}/{product}/draft',
                data={'method_version':'approved-method-v1','template_version':'candidate-template-v1'},
                files={'file':(f'Level2-{product}.docx',word_bytes(f'Level 2 {product}'),
                    'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert draft.status_code==200,draft.text
            row=draft.json();level2_reports[product]=row
            assert row['display_title']==f'Example Member - {product} Level 2A'
            matrix=reviewer.post(f'/api/package-reports/{row["id"]}/conformance',
                json={'content_sha256':row['content_sha256'],'checks':complete_checks,
                    'summary':'Fictional exact-version Level 2 Charter review for chain testing.'})
            assert matrix.status_code==200,matrix.text
            archive=assigned_owner.post(f'/api/package-reports/{row["id"]}/qa-evidence',
                files={'file':(f'Level2-{product}-qa.zip',qa_zip({**complete_manifest,
                    'report_sha256':row['content_sha256']}),'application/zip')})
            assert archive.status_code==200,archive.text
            reviewed=reviewer.post(f'/api/package-reports/{row["id"]}/qa-reviews',
                json={**review_payload,'evidence_id':archive.json()['id']})
            assert reviewed.status_code==200,reviewed.text
        level2_sources={product:{'report_id':level2_reports[product]['id'],
            'content_sha256':level2_reports[product]['content_sha256'],'alignment':'Aligned',
            'explanation':'Fictional Level 2 exact-source comparison for the chain.'}
            for product in ('SalINTEL','SalTHIRA','SalOPS')}
        level2_comparison=reviewer.post(
            f'/api/package-reports/{level2_reports["SalCAPA"]["id"]}/source-reconciliation',
            json={'salcapa_sha256':level2_reports['SalCAPA']['content_sha256'],
                'sources':level2_sources,'summary':'Fictional Level 2 comparison of all three source reports.'})
        assert level2_comparison.status_code==200,level2_comparison.text
        level2_issue=reviewer.post(f'/api/assessments/{next_assessment_id}/package-issues',
            json={'report_ids':{product:row['id'] for product,row in level2_reports.items()},
                'recipient_user_id':user_id,
                'issue_basis':'Fictional independent Level 2 release decision for the exact four reports.',
                'confirm_qualified_release':True})
        assert level2_issue.status_code==200 and level2_issue.json()['status']=='Issued',level2_issue.text
        for product in level2_reports:
            delivered=member.get(f'/api/package-issues/{level2_issue.json()["id"]}/reports/{product}.docx')
            assert delivered.status_code==200,delivered.text
        level2_ack=member.post(f'/api/package-issues/{level2_issue.json()["id"]}/acknowledgment',
            json={'issue_sha256':level2_issue.json()['record_sha256'],
                'confirm_received':True,'confirm_reviewed_limitations':True,
                'acknowledgment_note':'Fictional Member confirms Level 2 receipt and limits.',
                'idempotency_key':'fictional-level2-receipt'})
        assert level2_ack.status_code==200,level2_ack.text
        level2_qualification=assigned_owner.post(
            f'/api/assessments/{next_assessment_id}/package-predecessor-qualifications',
            json={'issue_sha256':level2_issue.json()['record_sha256'],
                'acknowledgment_id':level2_ack.json()['id'],
                'qualification_basis':'Fictional independent Level 2 review of the exact issued package.',
                'limitations_disposition':'Fictional Level 2 limitations remain visible to the Level 3 buyer.',
                'confirm_independent_review':True})
        assert level2_qualification.status_code==200,level2_qualification.text
        level3_assessment=assigned_owner.post('/api/assessments',json={
            'name':'Deep same-boundary review','organization':'Example Member',
            'covered_operation':'One named operation','exclusions':'Other sites and functions',
            'requested_package_level':3,'requested_scope_band':'A','requested_access_variant':''})
        assert level3_assessment.status_code==200,level3_assessment.text
        level3_id=level3_assessment.json()['id']
        conn=app.db()
        conn.execute('INSERT INTO assessment_access(user_id,assessment_id,created_at) VALUES(?,?,?)',
            (salus_user,level3_id,app.now()))
        conn.commit();conn.close()
        level3_agreement=assigned_owner.post(f'/api/assessments/{level3_id}/package-agreements',
            files={'file':('Deep-Agreement.pdf',pdf,'application/pdf')})
        assert level3_agreement.status_code==200,level3_agreement.text
        level3_quote=assigned_owner.post(f'/api/assessments/{level3_id}/package-quote',
            json={**next_quote,'level':3,'fee_cents':1250000,
                'agreement_artifact_id':level3_agreement.json()['id'],
                'agreement_reference':'DEEP-AGREEMENT-1',
                'predecessor_qualification_id':level2_qualification.json()['id']})
        assert level3_quote.status_code==200 and level3_quote.json()['level']==3,level3_quote.text
        deep_review=assigned_owner.post(f'/api/assessments/{level3_id}/package-member-authority',
            json={**authority_review,'quote_id':level3_quote.json()['id']})
        assert deep_review.status_code==200,deep_review.text
        assert member.get(f'/api/package-agreements/{level3_agreement.json()["id"]}/download').status_code==200
        level3_accept=member.post(f'/api/assessments/{level3_id}/package-acceptance',json={
            **acceptance,'quote_id':level3_quote.json()['id'],
            'quote_sha256':level3_quote.json()['content_sha256'],
            'idempotency_key':'member-acceptance-level3'})
        assert level3_accept.status_code==200 and level3_accept.json()['status']=='Authorized',level3_accept.text
        assert member.get(issue_url).json()['issues'][0]['acknowledged_at']==acknowledged.json()['acknowledged_at']
        assert member.post(acknowledgment_url,json=acknowledgment_payload).json()['idempotent'] is True
        assert member.post(acknowledgment_url,json={**acknowledgment_payload,
            'acknowledgment_note':'A different fictional decision using the same key.'}).status_code==409
        assert reviewer.post(acknowledgment_url,json=acknowledgment_payload).status_code==403
        conn=app.db()
        conn.execute('UPDATE package_report_issue_packets SET issue_basis=? WHERE id=?',
            ('Altered issue basis without a new immutable release.',issued_packet.json()['id']))
        conn.commit();conn.close()
        assert member.get(issue_url).status_code==409
        conn=app.db()
        conn.execute('UPDATE package_report_issue_packets SET issue_basis=? WHERE id=?',
            (issue_payload['issue_basis'],issued_packet.json()['id']))
        conn.commit();conn.close()
        requested=member.get(intake_url)
        assert requested.status_code==200 and len(requested.json()['items'])==2,requested.text
        assert other_member.get(intake_url).status_code==403
        assert requested.json()['catalog']==[]
        assert member.get(report_url).status_code==403
        assert member.get(f'/api/package-reports/{revised.json()["id"]}/draft.docx').status_code==403
        assert member.get(qa_url).status_code==403
        assert member.get(qa_archive_url).status_code==403
        assert member.get(review_url).status_code==403
        assert member.get(reconciliation_url).status_code==403
        assert member.get(preflight_url).status_code==403
        assert member.patch(retention_url,json={'legal_hold':True,'reason':'No Member retention authority in this candidate.'}).status_code==403
        assert 'response_user_id' not in requested.json()['items'][0]
        upload_item=requested.json()['items'][1]['id']
        upload_path=f'{intake_url}/{upload_item}/files'
        upload_bytes=b'%PDF-1.4\\nfictional requested record\\n%%EOF'
        original_scan=app.scan_bytes
        def unexpected_scan(content,filename):
            raise AssertionError('An invalid or unauthorized intake item must not invoke the scanner')
        app.scan_bytes=unexpected_scan
        assert member.post(f'{intake_url}/999999/files',files={'file':('Unrequested.pdf',upload_bytes,'application/pdf')}).status_code==404
        assert other_member.post(upload_path,files={'file':('Unrequested.pdf',upload_bytes,'application/pdf')}).status_code==403
        app.scan_bytes=original_scan
        uploaded=member.post(upload_path,files={'file':('Example-Plan.pdf',upload_bytes,'application/pdf')})
        assert uploaded.status_code==200,uploaded.text
        file_id=uploaded.json()['id']
        assert uploaded.json()['content_sha256']==hashlib.sha256(upload_bytes).hexdigest()
        repeated_upload=member.post(upload_path,files={'file':('Example-Plan.pdf',upload_bytes,'application/pdf')})
        assert repeated_upload.status_code==200 and repeated_upload.json()['id']==file_id
        assert member.get(intake_url).json()['items'][1]['status']=='Provided'
        assert member.get(intake_url).json()['uploads'][0]['id']==file_id
        received=member.get(f'/api/package-intake-files/{file_id}/download')
        assert received.status_code==200 and received.content==upload_bytes
        assert other_member.get(f'/api/package-intake-files/{file_id}/download').status_code==403
        assert received.headers['x-content-sha256']==uploaded.json()['content_sha256']
        conn=app.db()
        conn.execute('UPDATE package_intake_uploads SET scan_status=? WHERE id=?',('Pending',file_id))
        conn.commit();conn.close()
        pending_file=member.get(f'/api/package-intake-files/{file_id}/download')
        assert pending_file.status_code==409 and 'security check' in pending_file.text,pending_file.text
        pending_file_retry=member.post(upload_path,
            files={'file':('Example-Plan.pdf',upload_bytes,'application/pdf')})
        assert pending_file_retry.status_code==409,pending_file_retry.text
        conn=app.db()
        conn.execute('UPDATE package_intake_uploads SET scan_status=? WHERE id=?',('Clean',file_id))
        conn.commit();conn.close()
        assert member.patch(f'{intake_url}/{upload_item}',json={'status':'Not held'}).status_code==409
        intake_retention=f'/api/package-intake-files/{file_id}/retention'
        assert member.patch(intake_retention,json={'legal_hold':True,
            'reason':'A Member cannot set the internal legal retention status.'}).status_code==403
        assert assigned_owner.patch(intake_retention,json={'retention_until':'2030-01-01T00:00:00Z',
            'reason':'Fictional attempt to shorten the default intake retention.'}).status_code==409
        preserved=assigned_owner.patch(intake_retention,json={'retention_until':'2099-01-01T00:00:00Z',
            'legal_hold':True,'reason':'Fictional Salus preservation and longer retention decision.'})
        assert preserved.status_code==200 and preserved.json()['legal_hold'] is True,preserved.text
        assert assigned_owner.patch(intake_retention,json={'retention_until':'2098-01-01T00:00:00Z',
            'reason':'Fictional attempt to shorten extended intake retention.'}).status_code==409
        assert member.post(upload_path,files={'file':('bad.exe',b'not allowed','application/octet-stream')}).status_code==422
        original_scan=app.scan_bytes
        app.scan_bytes=lambda content,filename:{'ok':False,'status':'Infected'}
        assert member.post(upload_path,files={'file':('Blocked.pdf',b'fictional blocked content','application/pdf')}).status_code==422
        app.scan_bytes=original_scan
        assert director.post(upload_path,files={'file':('Example-Plan.pdf',upload_bytes,'application/pdf')}).status_code in (401,403)
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
        assert other_tenant.get(f'/api/package-intake-files/{file_id}/download').status_code==404
        assert other_tenant.patch(intake_retention,json={'legal_hold':True,
            'reason':'Fictional cross-tenant preservation attempt must fail.'}).status_code in (403,404)
        assert other_tenant.get(report_url).status_code==403
        assert other_tenant.get(issue_url).status_code==403
        assert other_tenant.post(acknowledgment_url,json=acknowledgment_payload).status_code==403
        assert other_tenant.post(predecessor_url,json=predecessor_payload).status_code==403
        assert other_tenant.get(qa_archive_url).status_code in (403,404)
        assert other_tenant.get(reconciliation_url).status_code in (403,404)
        assert other_tenant.get(preflight_url).status_code==403
        admin=TestClient(app.app,headers={'X-Salus-Role':'System Administrator'})
        backup=admin.post('/api/admin/backups')
        assert backup.status_code==200, backup.text
        validation=admin.post(f"/api/admin/backups/{backup.json()['id']}/dr-validate")
        assert validation.status_code==200 and validation.json()['ok'], validation.text
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_agreement_artifacts').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_agreement_downloads').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_quote_predecessor_links').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_intake_requests').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_intake_uploads').fetchone()[0]==1
        assert conn.execute('SELECT legal_hold FROM package_intake_uploads WHERE id=?',(file_id,)).fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_product_report_versions').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_conformance').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_reconciliations').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_report_qa_evidence').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_qa_reviews').fetchone()[0]==8
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_packets').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_deliveries').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_acknowledgments').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_predecessor_qualifications').fetchone()[0]==2
        assert conn.execute('SELECT legal_hold FROM package_product_report_versions WHERE id=?',
            (revised.json()['id'],)).fetchone()[0]==1
        assert conn.execute('SELECT status FROM package_intake_requests WHERE id=?',(item_id,)).fetchone()[0]=='Not held'
        from portable_backup import collect_tenant_records, replace_tenant_records, validate_records
        records=collect_tenant_records(conn,1)
        assert len(records['package_quote_versions'])==3
        assert len(records['package_agreement_artifacts'])==3
        assert len(records['package_agreement_downloads'])==3
        assert len(records['package_acceptances'])==3
        assert len(records['package_quote_predecessor_links'])==2
        assert len(records['package_intake_requests'])==2
        assert len(records['package_intake_uploads'])==1
        saved_intake_upload=records['package_intake_uploads'][0]
        pending_bytes=b'fictional unscanned original'
        pending_digest=hashlib.sha256(pending_bytes).hexdigest()
        class FakeQuarantine:
            calls=0
            def stage_bytes(self,*,tenant_id,assessment_id,quote_id,intake_request_id,data):
                self.calls+=1
                name=(f'tenant-{tenant_id}/assessment-{assessment_id}/quote-{quote_id}/'
                      f'item-{intake_request_id}/'+ 'a'*32+'_'+hashlib.sha256(data).hexdigest()[:16])
                return {'tenant_id':tenant_id,'assessment_id':assessment_id,'quote_id':quote_id,
                        'intake_request_id':intake_request_id,'status':'Pending','blob_name':name,
                        'blob_uri':'https://salusquarantine.blob.core.windows.net/quarantine/'+name,
                        'blob_version_id':'v1','etag':'"0xE1"',
                        'sha256':hashlib.sha256(data).hexdigest(),'size_bytes':len(data)}
        fake_quarantine=FakeQuarantine()
        app.package_quarantine=lambda:fake_quarantine
        app.PACKAGE_SCAN_MODE='defender'
        app.AUTH_MODE='session'
        held=member.post(upload_path,files={'file':('pending.txt',pending_bytes,'text/plain')})
        assert held.status_code==200 and held.json()['scan_status']=='Pending',held.text
        held_repeat=member.post(upload_path,files={'file':('pending.txt',pending_bytes,'text/plain')})
        assert held_repeat.status_code==200 and held_repeat.json()['id']==held.json()['id']
        assert fake_quarantine.calls==1
        assert member.get(intake_url).json()['pending_uploads'][0]['id']==held.json()['id']
        app.AUTH_MODE='prototype'
        app.PACKAGE_SCAN_MODE='inline'
        records=collect_tenant_records(conn,1)
        assert len(records['package_intake_pending_scans'])==1
        assert not validate_records(records,1)
        tampered_pending=dict(records['package_intake_pending_scans'][0])
        tampered_pending['blob_version_id']=''
        records['package_intake_pending_scans']=[tampered_pending]
        assert any('package pending scan' in error for error in validate_records(records,1))
        records['package_intake_pending_scans']=[dict(tampered_pending,blob_version_id='v1')]
        held_backup=admin.post('/api/admin/backups')
        assert held_backup.status_code==200,held_backup.text
        held_dr=admin.post(f"/api/admin/backups/{held_backup.json()['id']}/dr-validate")
        assert held_dr.status_code==200 and not held_dr.json()['ok']
        assert any('Quarantined originals' in error for error in held_dr.json()['errors'])
        invalid_intake=dict(saved_intake_upload); invalid_intake['quote_id']=999999
        records['package_intake_uploads']=[invalid_intake]
        assert any('package intake file' in error for error in validate_records(records,1))
        records['package_intake_uploads']=[saved_intake_upload]
        assert len(records['package_product_report_versions'])==9
        assert len(records['package_report_conformance'])==9
        assert len(records['package_report_reconciliations'])==3
        assert len(records['package_report_qa_evidence'])==9
        assert len(records['package_report_qa_reviews'])==8
        assert len(records['package_report_issue_packets'])==2
        assert len(records['package_report_issue_deliveries'])==9
        assert len(records['package_report_issue_acknowledgments'])==2
        assert len(records['package_predecessor_qualifications'])==2
        assert not validate_records(records,1)
        original_manifest_hash=records['package_report_qa_evidence'][0]['manifest_sha256']
        records['package_report_qa_evidence'][0]['manifest_sha256']='0'*64
        assert any('invalid immutable proof' in error for error in validate_records(records,1))
        records['package_report_qa_evidence'][0]['manifest_sha256']=original_manifest_hash
        original_comparison=records['package_report_reconciliations'][0]['summary']
        records['package_report_reconciliations'][0]['summary']='Altered after the source comparison was created.'
        assert any('immutable source verification' in error for error in validate_records(records,1))
        records['package_report_reconciliations'][0]['summary']=original_comparison
        original_summary=records['package_report_conformance'][0]['summary']
        records['package_report_conformance'][0]['summary']='Altered after the conformance record was created.'
        assert any('immutable matrix verification' in error for error in validate_records(records,1))
        records['package_report_conformance'][0]['summary']=original_summary
        original_ack_note=records['package_report_issue_acknowledgments'][0]['acknowledgment_note']
        records['package_report_issue_acknowledgments'][0]['acknowledgment_note']='Altered receipt.'
        assert any('invalid receipt proof' in error for error in validate_records(records,1))
        records['package_report_issue_acknowledgments'][0]['acknowledgment_note']=original_ack_note
        original_qual_limit=records['package_predecessor_qualifications'][0]['limitations_disposition']
        records['package_predecessor_qualifications'][0]['limitations_disposition']='Altered limits.'
        assert any('invalid predecessor proof' in error for error in validate_records(records,1))
        records['package_predecessor_qualifications'][0]['limitations_disposition']=original_qual_limit
        original_link_sha=records['package_quote_predecessor_links'][0]['qualification_sha256']
        records['package_quote_predecessor_links'][0]['qualification_sha256']='0'*64
        assert any('invalid prerequisite proof' in error for error in validate_records(records,1))
        records['package_quote_predecessor_links'][0]['qualification_sha256']=original_link_sha
        replace_tenant_records(conn,1,records)
        conn.commit()
        assert conn.execute('SELECT status FROM package_intake_pending_scans WHERE tenant_id=1').fetchone()[0]=='Reconcile'
        assert conn.execute('SELECT COUNT(*) FROM package_quote_versions').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_acceptances').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_quote_predecessor_links').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_intake_requests').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_intake_uploads').fetchone()[0]==1
        assert conn.execute('SELECT COUNT(*) FROM package_product_report_versions').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_conformance').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_reconciliations').fetchone()[0]==3
        assert conn.execute('SELECT COUNT(*) FROM package_report_qa_evidence').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_qa_reviews').fetchone()[0]==8
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_packets').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_deliveries').fetchone()[0]==9
        assert conn.execute('SELECT COUNT(*) FROM package_report_issue_acknowledgments').fetchone()[0]==2
        assert conn.execute('SELECT COUNT(*) FROM package_predecessor_qualifications').fetchone()[0]==2
        assert conn.execute('SELECT legal_hold FROM package_product_report_versions WHERE id=?',
            (revised.json()['id'],)).fetchone()[0]==1
        assert conn.execute('SELECT status FROM package_intake_requests WHERE id=?',(item_id,)).fetchone()[0]=='Not held'
        # Simulate a separately reconciled held original and an authenticated
        # queue result. The restored Reconcile status must never auto-promote.
        held_quote_id=conn.execute('SELECT quote_id FROM package_intake_pending_scans WHERE id=?',
            (held.json()['id'],)).fetchone()[0]
        conn.execute("UPDATE package_intake_pending_scans SET status='Pending' WHERE id=?",(held.json()['id'],))
        conn.commit();conn.close()
        def fake_read_version(manifest):
            assert manifest['status']=='Pending' and manifest['sha256']==pending_digest
            return {'blob_uri':manifest['blob_uri'],'blob_version_id':'v1',
                    'etag':'"0xE1"','bytes':pending_bytes}
        fake_quarantine.read_version=fake_read_version
        app.PACKAGE_SCAN_MODE='defender'
        topic='/subscriptions/test/resourceGroups/test/providers/Microsoft.EventGrid/topics/test'
        blob_uri='https://salusquarantine.blob.core.windows.net/quarantine/'+(
            f'tenant-1/assessment-{assessment_id}/quote-{held_quote_id}/item-{item_id}/'
            + 'a'*32+'_'+pending_digest[:16])
        result_event={'id':'event-1','eventType':'Microsoft.Security.MalwareScanningResult',
            'topic':topic,'data':{'blobUri':blob_uri,'eTag':'"0xE1"',
            'scanResultType':'No threats found','scanResultDetails':{
                'sha256':pending_digest,'malwareNamesFound':[]}}}
        assert app.process_package_scan_result(result_event,quarantine=fake_quarantine,
            expected_topic=topic)=='Promoted'
        assert app.process_package_scan_result(result_event,quarantine=fake_quarantine,
            expected_topic=topic)=='Promoted'
        conn=app.db()
        promoted=conn.execute('SELECT * FROM package_intake_uploads WHERE content_sha256=?',
            (pending_digest,)).fetchone()
        assert promoted and app.storage.get_bytes(promoted['stored_name'])==pending_bytes
        assert conn.execute('SELECT COUNT(*) FROM package_intake_uploads').fetchone()[0]==2
        promoted_id=promoted['id'];conn.close()
        contrary=json.loads(json.dumps(result_event)); contrary['id']='event-2'
        contrary['data']['scanResultType']='Malicious'
        assert app.process_package_scan_result(contrary,quarantine=fake_quarantine,
            expected_topic=topic)=='Reconcile'
        conn=app.db()
        assert conn.execute('SELECT scan_status FROM package_intake_uploads WHERE id=?',
            (promoted_id,)).fetchone()[0]=='Reconcile'
        assert not validate_records(collect_tenant_records(conn,1),1)
        app.PACKAGE_SCAN_MODE='inline'
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
        assert blocked.status_code==409 and 'exact qualified prior package' in blocked.text
    ''')
    child = tmp_path / 'workflow_child.py'
    child.write_text(program, encoding='utf-8')
    result = subprocess.run([sys.executable, str(child)], env=env, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
