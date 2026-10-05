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
            'Version and effective date  Standard terms revision 10, 5 October 2026; '
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
    ''')
    completed=subprocess.run([sys.executable,'-c',program],cwd=os.getcwd(),
                             env=env,capture_output=True,text=True,timeout=45)
    assert completed.returncode==0,completed.stdout+completed.stderr
