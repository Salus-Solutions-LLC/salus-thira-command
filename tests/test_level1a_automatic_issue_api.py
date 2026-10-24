"""A signed-in buyer can issue and retry only the exact controlled Word bytes."""

import os
import subprocess
import sys
import textwrap
import pytest


@pytest.mark.parametrize('review_mode',['Independent','Single-operator'])
def test_signed_in_issue_retry_and_download(tmp_path,review_mode):
    env=os.environ.copy()
    env.update(SALUS_DB_PATH=str(tmp_path/'orders.db'),
               SALUS_LOCAL_STORAGE_DIR=str(tmp_path/'files'),
               SALUS_BACKUP_DIR=str(tmp_path/'backups'),
               SALUS_SEED_DEMO='0',SALUS_AUTH_MODE='session',
               SALUS_TEST_SOLO_REVIEW=str(review_mode=='Single-operator'),
               SALUS_LEVEL1A_ORDER_DRAFT_ENABLED='1',
               PYTHONPATH=os.pathsep.join(filter(None,(os.getcwd(),env.get('PYTHONPATH','')))))
    program=textwrap.dedent('''
        from docx import Document
        from fastapi.testclient import TestClient
        from hashlib import sha256
        from io import BytesIO
        import os
        import app
        import salus_level1a_agreement_ledger as ledger
        solo_mode=os.environ['SALUS_TEST_SOLO_REVIEW']=='True'

        doc=Document()
        for line in (
            'Protected Member legal name  [Complete before issue]',
            'Covered site address  [Complete before issue]',
            'Primary operating activity  [Complete before issue]',
            'Decision owner role and authorized signatory  [Complete before issue]',
            'Scope and quote identifier  [Complete before issue]',
            'Version and effective date  Standard terms revision 11, 9 October 2026; '
            'effective only on electronic Member acceptance of the completed issued version',
            'Included buildings and outdoor areas  [Complete before issue]',
            'Express exclusions  [Complete before issue]',
            'Applicable tax and total  [Complete before issue]',
        ):
            doc.add_paragraph(line)
        stream=BytesIO();doc.save(stream);template=stream.getvalue()
        digest=sha256(template).hexdigest()
        # The production digest is fixed. Substitute only inside this isolated
        # fictional test process so CI needs no separate controlled binary.
        ledger.APPROVED_TEMPLATE_SHA256=digest
        app.APPROVED_TEMPLATE_SHA256=digest
        app.APPROVED_TEMPLATE_KEY=f'level1a/templates/{digest}.docx'
        app.storage.put_bytes(app.APPROVED_TEMPLATE_KEY,template)
        conn=app.db()
        uid=conn.execute('INSERT INTO users (tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'buyer','Buyer','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions (user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (uid,app._hash_token('fictional-buyer-cookie'),
             '2099-01-01T00:00:00Z',app.now(),app.now()))
        staff_uid=conn.execute('INSERT INTO users (tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'fictional-report-owner','Fictional Report Owner','System Administrator','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions (user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (staff_uid,app._hash_token('fictional-staff-cookie'),
             '2099-01-01T00:00:00Z',app.now(),app.now()))
        reviewer_uid=conn.execute('INSERT INTO users (tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'fictional-report-reviewer','Fictional Report Reviewer','System Administrator','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions (user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (reviewer_uid,app._hash_token('fictional-reviewer-cookie'),
             '2099-01-01T00:00:00Z',app.now(),app.now()))
        other_uid=conn.execute('INSERT INTO users (tenant_id,username,display_name,role,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
            (1,'other-buyer','Other Buyer','Client Executive','Active',app.now(),app.now())).lastrowid
        conn.execute('INSERT INTO auth_sessions (user_id,token_hash,expires_at,created_at,last_seen_at) VALUES(?,?,?,?,?)',
            (other_uid,app._hash_token('other-buyer-cookie'),
             '2099-01-01T00:00:00Z',app.now(),app.now()))
        conn.commit();conn.close()
        buyer=TestClient(app.app,cookies={'salus_session':'fictional-buyer-cookie'})
        staff=TestClient(app.app,cookies={'salus_session':'fictional-staff-cookie'})
        reviewer=TestClient(app.app,cookies={'salus_session':'fictional-reviewer-cookie'})
        other_buyer=TestClient(app.app,cookies={'salus_session':'other-buyer-cookie'})
        outsider=TestClient(app.app)
        fields=dict(idempotency_key='fictional-route-00001',
            buyer_legal_name='Fictional Daycare LLC',unit_kind='Site',
            unit_name='Oak Street site',
            covered_boundary='One building and fenced playground',
            operating_activity='Child care',exclusions='All other locations',
            decision_owner_role='Chief executive',notice_email='example@example.test',
            service_use_address='100 Oak Street, Austin, Texas',
            service_use_postal_code='78701',use_country='US',use_region='TX')
        created=buyer.post('/api/level1a/orders',json=fields)
        assert created.status_code==200,created.text
        oid=created.json()['order_id']
        quote=buyer.post(f'/api/level1a/orders/{oid}/quote')
        assert quote.status_code==200,quote.text
        qid=quote.json()['quote_id']
        url=f'/api/level1a/orders/{oid}/agreements/issue'
        assert outsider.post(url,json={'quote_id':qid,'signer_name':'Jane Example'}).status_code in (401,403,503)
        issued=buyer.post(url,json={'quote_id':qid,'signer_name':'Jane Example'})
        assert issued.status_code==200,issued.text
        again=buyer.post(url,json={'quote_id':qid,'signer_name':'Jane Example'})
        assert again.status_code==200 and again.json()['idempotent'],again.text
        changed=buyer.post(url,json={'quote_id':qid,'signer_name':'Other Person'})
        assert changed.status_code==409
        aid=issued.json()['agreement_id']
        downloaded=buyer.get(f'/api/level1a/orders/{oid}/agreements/{aid}/download')
        assert downloaded.status_code==200,downloaded.text
        assert sha256(downloaded.content).hexdigest()==issued.json()['agreement_sha256']
        assert not issued.json()['checkout_available'] and not issued.json()['upload_available']
        accepted=buyer.post(f'/api/level1a/orders/{oid}/accept',json={
            'quote_id':qid,'agreement_id':aid,
            'agreement_sha256':issued.json()['agreement_sha256'],
            'typed_name':'Jane Example',
            'authority_basis':'Chief executive with contracting authority',
            'idempotency_key':'fictional-accept-00001',
            'accept_quote_and_agreement':True})
        assert accepted.status_code==200,accepted.text
        # Even if all public intake switches were mistakenly enabled, an
        # agreement and account alone cannot open or expose the intake.
        app.LEVEL1A_INTAKE_ENABLED=True
        app.LEVEL1A_UPLOAD_ENABLED=True
        app.PACKAGE_SCANNER_ACCEPTED=True
        app.PACKAGE_SCAN_MODE='defender'
        intake_base=f'/api/level1a/orders/{oid}/intake'
        assert buyer.post(f'{intake_base}/open').status_code==409
        assert buyer.get(intake_base).status_code==409
        assert buyer.post(f'{intake_base}/disclosure-authority',json={
            'authority_basis':'I am the records custodian for the named site',
            'confirm_authorized_disclosure':True}).status_code==409
        assert buyer.post(f'{intake_base}/1/files',files={
            'file':('early.pdf',b'unpaid fictional bytes','application/pdf')}).status_code==409
        assert buyer.get(f'{intake_base}/files/1/download').status_code==409
        conn=app.db()
        assert conn.execute('SELECT COUNT(*) AS n FROM level1a_assessment_links').fetchone()['n']==0
        assert conn.execute('SELECT COUNT(*) AS n FROM level1a_pending_scans').fetchone()['n']==0
        conn.close()
        app.LEVEL1A_INTAKE_ENABLED=False
        app.LEVEL1A_UPLOAD_ENABLED=False
        app.PACKAGE_SCANNER_ACCEPTED=False
        app.PACKAGE_SCAN_MODE=''
        app.secret=lambda key,default='': {
            'SALUS_STRIPE_SECRET_KEY':'rk_test_fictional',
            'SALUS_STRIPE_WEBHOOK_SECRET':'whsec_fictional'}.get(key,default)
        app.create_level1a_checkout_session=lambda *args,**kwargs: {
            'id':'cs_test_example12345678',
            'url':'https://checkout.stripe.com/c/pay/fictional'}
        app.os.environ['SALUS_PACKAGE_CHECKOUT_RETURN_ORIGIN']='https://salcapa.salus.solutions'
        # Draft ordering can be reviewed while checkout stays closed.
        mode=buyer.get('/api/system/mode').json()
        assert mode['level1a_draft_available'] and not mode['level1a_checkout_available']
        assert not mode['level1a_purchase_available']
        assert buyer.post(f'/api/level1a/orders/{oid}/checkout').status_code==503
        app.LEVEL1A_CHECKOUT_ENABLED=True
        started=buyer.post(f'/api/level1a/orders/{oid}/checkout')
        assert started.status_code==200 and started.json()['status']=='Pending',started.text
        pending=buyer.get(f'/api/level1a/orders/{oid}/checkout').json()
        assert pending['status']=='Pending' and pending['test_mode'] is True
        assert buyer.get('/api/level1a/orders/recoverable').json()['orders']==[]
        assert b'href="/?view=level1a"' in buyer.get(
            '/package-checkout-return?flow=level1a').content
        assert b'href="/?view=level1a"' in buyer.get(
            '/package-checkout-cancel?flow=level1a').content
        assert not buyer.get('/api/system/mode').json()['level1a_purchase_available']
        conn=app.db()
        binding=app.binding_for_accepted_order(conn,tenant_id=1,
            buyer_user_id=uid,order_id=oid)
        conn.close()
        paid_session={'id':'cs_test_example12345678','object':'checkout.session',
            'status':'complete','payment_status':'paid','mode':'payment',
            'livemode':False,'amount_subtotal':150000,'amount_total':150000,
            'currency':'usd','total_details':{'amount_tax':0},
            'client_reference_id':str(binding.acceptance_id),
            'metadata':binding.metadata(),'payment_intent':'pi_fictional'}
        app.retrieve_checkout_session=lambda session_id,key: paid_session
        import hmac,json,time
        def signed_event(event):
            payload=json.dumps(event,separators=(',',':')).encode()
            stamp=str(int(time.time()))
            signature=hmac.new(b'whsec_fictional',stamp.encode()+b'.'+payload,
                               'sha256').hexdigest()
            return buyer.post('/api/package-checkout/stripe-webhook',
                content=payload,headers={'Stripe-Signature':f't={stamp},v1={signature}'})
        payment=signed_event({'id':'evt_fictional_paid',
            'type':'checkout.session.completed',
            'data':{'object':{'id':'cs_test_example12345678'}}})
        assert payment.status_code==200 and payment.json()['outcome']=='Paid',payment.text
        repeated_payment=signed_event({'id':'evt_fictional_paid',
            'type':'checkout.session.completed',
            'data':{'object':{'id':'cs_test_example12345678'}}})
        assert repeated_payment.status_code==200 and repeated_payment.json()['outcome']=='Paid'
        verified=buyer.get(f'/api/level1a/orders/{oid}/checkout').json()
        assert verified['status']=='Paid' and verified['test_mode'] is True
        assert verified['receipt_available'] and not verified['upload_available']
        recovered=buyer.get('/api/level1a/orders/recoverable')
        assert recovered.status_code==200,recovered.text
        assert recovered.json()['orders']==[{'order_id':oid,
            'scope_sha256':binding.scope_sha256,'unit_name':'Oak Street site'}]
        outsider_orders=outsider.get('/api/level1a/orders/recoverable')
        assert outsider_orders.status_code in (401,403) or outsider_orders.json()['orders']==[]
        receipt=buyer.get(f'/api/level1a/orders/{oid}/receipt')
        assert receipt.status_code==200 and b'Page 1 of 1' in receipt.content,receipt.text
        assert b'STRIPE SANDBOX' in receipt.content and b'NO LIVE CHARGE' in receipt.content
        assert outsider.get(f'/api/level1a/orders/{oid}/receipt').status_code in (401,403,503)
        assert buyer.post(f'/api/level1a/orders/{oid}/intake/open').status_code==503
        app.LEVEL1A_INTAKE_ENABLED=True
        assert outsider.post(f'/api/level1a/orders/{oid}/intake/open').status_code in (401,403)
        opened=buyer.post(f'/api/level1a/orders/{oid}/intake/open')
        assert opened.status_code==200,opened.text
        assessment_id=opened.json()['assessment_id']
        conn=app.db()
        try:
            assessment=conn.execute('SELECT purpose FROM assessments WHERE id=?',(assessment_id,)).fetchone()
            assert assessment['purpose']=='Level 1A Assessment'
            source=conn.execute('SELECT * FROM level1a_report_sources WHERE order_id=? AND assessment_id=?',
                (oid,assessment_id)).fetchone()
            assert source and source['buyer_user_id']==uid
            assert source['scope_sha256']==binding.scope_sha256
            checkout=conn.execute('SELECT receipt_document_sha256 FROM level1a_checkout_sessions WHERE id=?',
                (source['checkout_id'],)).fetchone()
            assert source['receipt_document_sha256']==checkout['receipt_document_sha256']
            from salus_level1a_report_source import _digest
            assert source['record_sha256']==_digest(source)
            assert conn.execute('SELECT COUNT(*) n FROM package_quote_versions').fetchone()['n']==0
            assert conn.execute('SELECT COUNT(*) n FROM package_acceptances').fetchone()['n']==0
        finally:
            conn.close()
        again=buyer.post(f'/api/level1a/orders/{oid}/intake/open')
        assert again.status_code==200 and again.json()['idempotent']
        assert again.json()['assessment_id']==assessment_id
        source_url=f'/api/assessments/{assessment_id}/level1a-report-source'
        assert buyer.get(source_url).status_code==403
        source_read=staff.get(source_url)
        assert source_read.status_code==200 and source_read.json()['status']=='Verified',source_read.text
        assert source_read.json()['order_id']==oid
        draft_url=f'/api/assessments/{assessment_id}/level1a-reports/SalINTEL/draft'
        draft_form={'method_version':'fictional-method-1','template_version':'fictional-template-1'}
        app.scan_bytes=lambda content,name: {'ok':False,'status':'Infected'}
        held_draft=staff.post(draft_url,data=draft_form,
            files={'file':('fictional.docx',template,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert held_draft.status_code==422
        app.scan_bytes=lambda content,name: {'ok':True,'status':'Clean'}
        assert buyer.post(draft_url,data=draft_form,
            files={'file':('fictional.docx',template,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}).status_code==403
        draft=staff.post(draft_url,data=draft_form,
            files={'file':('fictional.docx',template,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert draft.status_code==200 and draft.json()['status']=='Draft',draft.text
        duplicate=staff.post(draft_url,data=draft_form,
            files={'file':('fictional.docx',template,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
        assert duplicate.status_code==200 and duplicate.json()['id']==draft.json()['id']
        report_id=draft.json()['id']
        from reportlab.pdfgen.canvas import Canvas
        import zipfile
        pdf_buffer=BytesIO();canvas=Canvas(pdf_buffer)
        canvas.drawString(40,40,'Page 1 of 3');canvas.showPage()
        canvas.showPage()
        canvas.drawString(40,40,'Page 3 of 3');canvas.save()
        pdf=pdf_buffer.getvalue()
        manifest=dict(report_sha256=sha256(template).hexdigest(),
            pdf_sha256=sha256(pdf).hexdigest(),renderer='Fictional Word renderer',
            pages=[{'page':number,'checked_full_size':True,'note':'Full page checked.'}
                   for number in (1,2,3)],native_word='Checked',
            accessibility='Checked',parity='Checked',notes='Fictional full page inspection')
        archive_buffer=BytesIO()
        with zipfile.ZipFile(archive_buffer,'w') as archive_file:
            archive_file.writestr('manifest.json',json.dumps(manifest))
            archive_file.writestr('rendered.pdf',pdf)
        archive_bytes=archive_buffer.getvalue()
        qa_url=f'/api/level1a-reports/{report_id}/qa-evidence'
        assert buyer.post(qa_url,files={'file':('qa.zip',archive_bytes,'application/zip')}).status_code==403
        qa=staff.post(qa_url,files={'file':('qa.zip',archive_bytes,'application/zip')})
        assert qa.status_code==200,qa.text
        evidence_id=qa.json()['id']
        assert staff.post(qa_url,files={'file':('qa.zip',archive_bytes,'application/zip')}).json()['idempotent']
        checks={key:{'status':'Met','reason':'The fictional exact page evidence was reviewed.'}
                for key in app.PACKAGE_REPORT_QA_KEYS}
        conformance_url=f'/api/level1a-reports/{report_id}/conformance'
        assert buyer.post(conformance_url,json={'content_sha256':sha256(template).hexdigest(),
            'checks':checks,'summary':'Fictional reviewer checked all Charter items.'}).status_code==403
        matrix=reviewer.post(conformance_url,json={'content_sha256':sha256(template).hexdigest(),
            'checks':checks,'summary':'Fictional reviewer checked all Charter items.'})
        assert matrix.status_code==200 and matrix.json()['status']=='Marked',matrix.text
        review_url=f'/api/level1a-reports/{report_id}/qa-reviews'
        review=dict(evidence_id=evidence_id,decision='Reviewed',
            checks={key:True for key in app.PACKAGE_REPORT_REVIEW_KEYS},
            qualification_basis='Fictional assessment director trained for the exact method.',
            review_note='All fictional pages and source details were reviewed in this isolated test.')
        assert staff.post(review_url,json=review).status_code==409
        solo={**review,'review_mode':'Single-operator',
            'review_note':'Single-operator human review: every fictional page and source checked.'}
        assert staff.post(review_url,json=solo).status_code==403
        app.LEVEL1A_SOLO_REVIEWER_EMAIL='fictional-report-owner@example.test'
        app.LEVEL1A_SOLO_REVIEWER_OBJECT_ID='fictional-entra-object-id'
        app.LEVEL1A_SOLO_REVIEW_ORDER_ID=str(oid)
        conn=app.db()
        conn.execute('UPDATE users SET email=?,external_subject=?,identity_provider=? WHERE id=?',
            ('fictional-report-owner@example.test',
            'fictional-entra-object-id','entra',staff_uid))
        conn.commit();conn.close()
        # A session-mode login cannot activate the protected exception.
        assert staff.post(review_url,json=solo).status_code==403
        app.AUTH_MODE='oidc'
        approved_solo=staff.post(review_url,json=solo)
        assert approved_solo.status_code==200,approved_solo.text
        assert staff.post(review_url,json=solo).json()['idempotent']
        conn=app.db()
        stored=conn.execute('SELECT review_mode FROM level1a_report_qa_reviews WHERE id=?',
            (approved_solo.json()['id'],)).fetchone()
        assert stored['review_mode']=='Single-operator'
        conn.close()
        app.LEVEL1A_SOLO_REVIEWER_OBJECT_ID=''
        blocked_solo=staff.get(f'/api/assessments/{assessment_id}/level1a-report-readiness')
        assert 'SalINTEL: qualified human review missing' in blocked_solo.json()['blockers']
        app.LEVEL1A_SOLO_REVIEWER_OBJECT_ID='fictional-entra-object-id'
        if solo_mode:
            reviewer=staff
            review=solo
        else:
            app.AUTH_MODE='session'
        checked=reviewer.post(review_url,json=review)
        assert checked.status_code==200 and checked.json()['decision']=='Reviewed',checked.text
        assert reviewer.post(review_url,json=review).json()['idempotent']
        assert buyer.get(f'/api/level1a-reports/{report_id}/draft.docx').status_code in (404,405)
        readiness=reviewer.get(f'/api/assessments/{assessment_id}/level1a-report-readiness')
        assert readiness.status_code==200 and readiness.json()['status']=='Blocked',readiness.text
        assert any('SalTHIRA' in item for item in readiness.json()['blockers'])
        assert any('reconciliation' in item for item in readiness.json()['blockers'])
        report_ids={'SalINTEL':report_id}
        for product in ('SalTHIRA','SalOPS','SalCAPA'):
            draft_result=staff.post(
                f'/api/assessments/{assessment_id}/level1a-reports/{product}/draft',
                data=draft_form,files={'file':('fictional.docx',template,
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document')})
            assert draft_result.status_code==200,draft_result.text
            current_id=draft_result.json()['id'];report_ids[product]=current_id
            qa_result=staff.post(f'/api/level1a-reports/{current_id}/qa-evidence',
                files={'file':('qa.zip',archive_bytes,'application/zip')})
            assert qa_result.status_code==200,qa_result.text
            matrix_result=reviewer.post(f'/api/level1a-reports/{current_id}/conformance',
                json={'content_sha256':sha256(template).hexdigest(),
                      'checks':checks,'summary':'Fictional reviewer checked all Charter items.'})
            assert matrix_result.status_code==200,matrix_result.text
            review_result=reviewer.post(f'/api/level1a-reports/{current_id}/qa-reviews',
                json={**review,'evidence_id':qa_result.json()['id']})
            assert review_result.status_code==200,review_result.text
        issue_url=f'/api/assessments/{assessment_id}/level1a-report-issues'
        issue_body=dict(report_ids=report_ids,recipient_user_id=uid,
            issue_basis='Fictional qualified human review of every page and exact paid source.',
            confirm_qualified_release=True)
        blocked_issue=reviewer.post(issue_url,json=issue_body)
        assert blocked_issue.status_code==409 and 'reconciliation' in blocked_issue.text
        sources={product:{'report_id':report_ids[product],
            'content_sha256':sha256(template).hexdigest(),
            'alignment':'Aligned',
            'explanation':'The fictional source is aligned with the exact SalCAPA draft.'}
            for product in ('SalINTEL','SalTHIRA','SalOPS')}
        reconciled=reviewer.post(
            f'/api/level1a-reports/{report_ids["SalCAPA"]}/source-reconciliation',
            json={'salcapa_sha256':sha256(template).hexdigest(),
                  'sources':sources,
                  'summary':'All three fictional source reports align with SalCAPA.'})
        assert reconciled.status_code==200 and reconciled.json()['status']=='Compared',reconciled.text
        readiness=reviewer.get(f'/api/assessments/{assessment_id}/level1a-report-readiness')
        assert readiness.status_code==200 and not readiness.json()['blockers'],readiness.text
        issued=reviewer.post(issue_url,json=issue_body)
        assert issued.status_code==200 and issued.json()['status']=='Issued',issued.text
        issue_id=issued.json()['id']
        issued_list=buyer.get(f'/api/level1a/orders/{oid}/reports')
        assert issued_list.status_code==200 and issued_list.json()['issues'][0]['id']==issue_id,issued_list.text
        assert other_buyer.get(f'/api/level1a/orders/{oid}/reports').status_code==409
        assert outsider.get(f'/api/level1a-report-issues/{issue_id}').status_code in (401,403)
        assert other_buyer.get(f'/api/level1a-report-issues/{issue_id}').status_code==403
        assert other_buyer.get(f'/api/level1a-report-issues/{issue_id}/reports/SalINTEL.pdf').status_code==403
        assert reviewer.get(f'/api/level1a-report-issues/{issue_id}').status_code==403
        assert buyer.get(f'/api/level1a-report-issues/{issue_id}').status_code==200
        ack_url=f'/api/level1a-report-issues/{issue_id}/acknowledgment'
        ack=dict(issue_sha256=issued.json()['record_sha256'],confirm_received=True,
            confirm_reviewed_limitations=True,
            acknowledgment_note='I received and reviewed the fictional four-report packet.',
            idempotency_key='fictional-report-ack-0001')
        assert buyer.post(ack_url,json=ack).status_code==409
        for product in ('SalINTEL','SalTHIRA','SalOPS','SalCAPA'):
            downloaded=buyer.get(f'/api/level1a-report-issues/{issue_id}/reports/{product}.docx')
            assert downloaded.status_code==200 and downloaded.content==template,downloaded.text
            if product=='SalINTEL':
                pdf_download=buyer.get(f'/api/level1a-report-issues/{issue_id}/reports/{product}.pdf')
                assert pdf_download.status_code==200 and pdf_download.content==pdf,pdf_download.text
        acknowledged=buyer.post(ack_url,json=ack)
        assert acknowledged.status_code==200 and not acknowledged.json()['idempotent'],acknowledged.text
        assert buyer.post(ack_url,json=ack).json()['idempotent']
        conn=app.db()
        original_source_sha=conn.execute('SELECT record_sha256 FROM level1a_report_sources WHERE order_id=?',
            (oid,)).fetchone()['record_sha256']
        conn.execute('UPDATE level1a_report_sources SET record_sha256=? WHERE order_id=?',
            ('0'*64,oid));conn.commit();conn.close()
        assert buyer.get(f'/api/level1a-report-issues/{issue_id}').status_code==409
        conn=app.db();conn.execute('UPDATE level1a_report_sources SET record_sha256=? WHERE order_id=?',
            (original_source_sha,oid));conn.commit();conn.close()
        conn=app.db()
        try:
            assert conn.execute('SELECT COUNT(*) n FROM level1a_report_sources WHERE order_id=?',
                (oid,)).fetchone()['n']==1
        finally:
            conn.close()
        intake=buyer.get(f'/api/level1a/orders/{oid}/intake')
        assert intake.status_code==200 and len(intake.json()['items'])==7,intake.text
        assert not intake.json()['disclosure_authority_recorded']
        assert not intake.json()['upload_available']
        assert outsider.get(f'/api/level1a/orders/{oid}/intake').status_code in (401,403)
        import uuid
        class FictionalQuarantine:
            def __init__(self): self.objects={};self.wrong_version=False
            def stage_bytes(self,*,tenant_id,assessment_id,quote_id,intake_request_id,data):
                digest=sha256(data).hexdigest()
                name=(f'tenant-{tenant_id}/assessment-{assessment_id}/quote-{quote_id}/'
                      f'item-{intake_request_id}/{uuid.uuid4().hex}_{digest[:16]}')
                uri=f'https://fictionalscan.blob.core.windows.net/quarantine/{name}'
                manifest=dict(tenant_id=tenant_id,assessment_id=assessment_id,
                    quote_id=quote_id,intake_request_id=intake_request_id,
                    status='Pending',blob_name=name,blob_uri=uri,
                    blob_version_id='fictional-v1',etag='"0xABC"',sha256=digest,
                    size_bytes=len(data))
                self.objects[uri]=(manifest,data)
                return manifest
            def read_version(self,manifest):
                saved,data=self.objects[manifest['blob_uri']]
                assert saved['blob_version_id']==manifest['blob_version_id']
                return {'blob_uri':saved['blob_uri'],
                        'blob_version_id':'different-version' if self.wrong_version
                                          else saved['blob_version_id'],
                        'etag':saved['etag'],'bytes':data}
        quarantine=FictionalQuarantine()
        app.package_quarantine=lambda **kwargs: quarantine
        app.PACKAGE_SCAN_MODE='defender'
        app.PACKAGE_SCANNER_ACCEPTED=True
        app.LEVEL1A_UPLOAD_ENABLED=True
        item_id=intake.json()['items'][0]['id']
        response_url=f'/api/level1a/orders/{oid}/intake/{item_id}/response'
        assert outsider.patch(response_url,json={'status':'Not held'}).status_code in (401,403)
        answered=buyer.patch(response_url,json={'status':'Not held'})
        assert answered.status_code==200 and answered.json()['idempotent'] is False,answered.text
        assert buyer.get(intake_base).json()['items'][0]['status']=='Not held'
        assert buyer.patch(response_url,json={'status':'Not held'}).json()['idempotent'] is True
        assert buyer.patch(response_url,json={'status':'Invalid'}).status_code==422
        reset=buyer.patch(response_url,json={'status':'Requested'})
        assert reset.status_code==200 and reset.json()['status']=='Requested'
        denied=buyer.post(f'/api/level1a/orders/{oid}/intake/{item_id}/files',
            files={'file':('clean.pdf',b'fictional clean PDF','application/pdf')})
        assert denied.status_code==403,denied.text
        asserted=buyer.post(f'/api/level1a/orders/{oid}/intake/disclosure-authority',
            json={'authority_basis':'I am the records custodian for the named site',
                  'confirm_authorized_disclosure':True})
        assert asserted.status_code==200,asserted.text
        assert buyer.get(f'/api/level1a/orders/{oid}/intake').json()['disclosure_authority_recorded']
        assert asserted.json()['upload_available']
        assert buyer.patch(response_url,json={'status':'Prefer to discuss'}).status_code==200
        assert buyer.post(f'/api/level1a/orders/{oid}/intake/{item_id}/files',
            files={'file':('blocked.pdf',b'fictional bytes','application/pdf')}).status_code==409
        assert buyer.patch(response_url,json={'status':'Requested'}).status_code==200
        clean=buyer.post(f'/api/level1a/orders/{oid}/intake/{item_id}/files',
            files={'file':('clean.pdf',b'fictional clean PDF','application/pdf')})
        assert clean.status_code==200 and clean.json()['scan_status']=='Pending',clean.text
        assert buyer.patch(response_url,json={'status':'Not known'}).status_code==409
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code==404
        clean_uri=next(iter(quarantine.objects))
        topic='/subscriptions/fictional/resourceGroups/test/providers/Microsoft.EventGrid/topics/scan'
        clean_event={'id':'fictional-clean-event','topic':topic,
            'eventType':'Microsoft.Security.MalwareScanningResult',
            'data':{'blobUri':clean_uri,'eTag':'0xABC',
                    'scanResultType':'No threats found'}}
        wrong_etag={**clean_event,'id':'fictional-wrong-etag',
            'data':{**clean_event['data'],'eTag':'0xDEF'}}
        assert app.process_level1a_scan_result(wrong_etag,quarantine=quarantine,
            expected_topic=topic)=='Unmatched'
        quarantine.wrong_version=True
        assert app.process_level1a_scan_result(clean_event,quarantine=quarantine,
            expected_topic=topic)=='Unmatched'
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code==404
        quarantine.wrong_version=False
        assert app.process_trusted_scan_result(clean_event,
            expected_topic=topic)=='Promoted'
        assert app.process_trusted_scan_result(clean_event,
            expected_topic=topic)=='Promoted'
        clean_download=buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download')
        assert clean_download.status_code==200 and clean_download.content==b'fictional clean PDF'
        assert outsider.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code in (401,403)
        eicar=buyer.post(f'/api/level1a/orders/{oid}/intake/{item_id}/files',
            files={'file':('eicar.txt',b'fictional adverse bytes','text/plain')})
        assert eicar.status_code==200 and eicar.json()['scan_status']=='Pending',eicar.text
        malicious_uri=list(quarantine.objects)[1]
        malicious={'id':'fictional-malicious-event','topic':topic,
            'eventType':'Microsoft.Security.MalwareScanningResult',
            'data':{'blobUri':malicious_uri,'eTag':'0xABC',
                    'scanResultType':'Malicious'}}
        assert app.process_trusted_scan_result(malicious,
            expected_topic=topic)=='Malicious'
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/2/download').status_code==404
        contrary={**clean_event,'id':'fictional-later-adverse',
            'data':{**clean_event['data'],'scanResultType':'Malicious'}}
        assert app.process_level1a_scan_result(contrary,quarantine=quarantine,
            expected_topic=topic)=='Reconcile'
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code==404
        refund=signed_event({'id':'evt_fictional_refund',
            'type':'charge.refunded',
            'data':{'object':{'payment_intent':'pi_fictional'}}})
        assert refund.status_code==200 and refund.json()['outcome']=='Held',refund.text
        assert buyer.get('/api/level1a/orders/recoverable').json()['orders']==[]
        assert buyer.get(f'/api/level1a/orders/{oid}/receipt').status_code==404
        assert buyer.get(f'/api/level1a/orders/{oid}/intake').status_code==409
        assert staff.get(source_url).status_code==409
        assert buyer.get(f'/api/level1a-report-issues/{issue_id}').status_code==409
        assert buyer.get(f'/api/level1a/orders/{oid}/reports').status_code==409
        assert buyer.get(f'/api/level1a-report-issues/{issue_id}/reports/SalINTEL.docx').status_code==409
        assert staff.post(draft_url,data=draft_form,
            files={'file':('fictional.docx',template,'application/vnd.openxmlformats-officedocument.wordprocessingml.document')}).status_code==409
        assert buyer.patch(response_url,json={'status':'Prefer to discuss'}).status_code==409
        assert buyer.patch(f'{intake_base}/1/response',json={'status':'Not held'}).status_code==409
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code==409
    ''')
    completed=subprocess.run([sys.executable,'-c',program],cwd=os.getcwd(),
                             env=env,capture_output=True,text=True,timeout=45)
    assert completed.returncode==0,completed.stdout+completed.stderr
