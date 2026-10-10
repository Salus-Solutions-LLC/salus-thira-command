"""A signed-in buyer can issue and retry only the exact controlled Word bytes."""

import os
import subprocess
import sys
import textwrap


def test_signed_in_issue_retry_and_download(tmp_path):
    env=os.environ.copy()
    env.update(SALUS_DB_PATH=str(tmp_path/'orders.db'),
               SALUS_LOCAL_STORAGE_DIR=str(tmp_path/'files'),
               SALUS_BACKUP_DIR=str(tmp_path/'backups'),
               SALUS_SEED_DEMO='0',SALUS_AUTH_MODE='session',
               SALUS_LEVEL1A_ORDER_DRAFT_ENABLED='1',
               PYTHONPATH=os.pathsep.join(filter(None,(os.getcwd(),env.get('PYTHONPATH','')))))
    program=textwrap.dedent('''
        from docx import Document
        from fastapi.testclient import TestClient
        from hashlib import sha256
        from io import BytesIO
        import app
        import salus_level1a_agreement_ledger as ledger

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
        conn.commit();conn.close()
        buyer=TestClient(app.app,cookies={'salus_session':'fictional-buyer-cookie'})
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
        # Draft ordering alone must never create a Stripe session.
        assert buyer.post(f'/api/level1a/orders/{oid}/checkout').status_code==503
        app.LEVEL1A_CHECKOUT_ENABLED=True
        started=buyer.post(f'/api/level1a/orders/{oid}/checkout')
        assert started.status_code==200 and started.json()['status']=='Pending',started.text
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
        receipt=buyer.get(f'/api/level1a/orders/{oid}/receipt')
        assert receipt.status_code==200 and b'Page 1 of 1' in receipt.content,receipt.text
        assert outsider.get(f'/api/level1a/orders/{oid}/receipt').status_code in (401,403,503)
        assert buyer.post(f'/api/level1a/orders/{oid}/intake/open').status_code==503
        app.LEVEL1A_INTAKE_ENABLED=True
        assert outsider.post(f'/api/level1a/orders/{oid}/intake/open').status_code in (401,403)
        opened=buyer.post(f'/api/level1a/orders/{oid}/intake/open')
        assert opened.status_code==200,opened.text
        assessment_id=opened.json()['assessment_id']
        again=buyer.post(f'/api/level1a/orders/{oid}/intake/open')
        assert again.status_code==200 and again.json()['idempotent']
        assert again.json()['assessment_id']==assessment_id
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
        assert buyer.get(f'/api/level1a/orders/{oid}/receipt').status_code==404
        assert buyer.get(f'/api/level1a/orders/{oid}/intake').status_code==409
        assert buyer.patch(response_url,json={'status':'Prefer to discuss'}).status_code==409
        assert buyer.patch(f'{intake_base}/1/response',json={'status':'Not held'}).status_code==409
        assert buyer.get(f'/api/level1a/orders/{oid}/intake/files/1/download').status_code==409
    ''')
    completed=subprocess.run([sys.executable,'-c',program],cwd=os.getcwd(),
                             env=env,capture_output=True,text=True,timeout=45)
    assert completed.returncode==0,completed.stdout+completed.stderr
