"""Buyer acceptance must lock only the exact issued Word and current price."""

import sqlite3
from hashlib import sha256

import pytest

from salus_level1a_acceptance import (ACCEPTANCE_TABLE_SQL,
                                      AcceptanceConflict, CONSENT_TEXT_V1,
                                      accept_issued_agreement)
from salus_level1a_agreement_ledger import (AGREEMENT_TABLE_SQL,
    AgreementConflict, record_generated_candidate, record_issued_download)
from salus_level1a_order_ledger import ORDER_TABLE_SQL, OrderConflict, save_draft, correct_draft
from salus_level1a_quote import QUOTE_TABLE_SQL, quote_for_order


def _setup():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.executescript('''CREATE TABLE tenants(id INTEGER PRIMARY KEY);
        CREATE TABLE users(id INTEGER PRIMARY KEY);
        INSERT INTO tenants(id) VALUES(1),(2);
        INSERT INTO users(id) VALUES(11),(22);''')
    for script in (ORDER_TABLE_SQL,QUOTE_TABLE_SQL,AGREEMENT_TABLE_SQL,
                   ACCEPTANCE_TABLE_SQL):
        conn.executescript(script)
    values=dict(buyer_legal_name='Example Care LLC',unit_kind='Site',
        unit_name='Oak Street daycare',covered_boundary='One building and playground',
        operating_activity='Child care',exclusions='Other locations',
        decision_owner_role='Chief executive',notice_email='buyer@example.test',
        service_use_address='100 Oak Street, Austin, Texas',
        service_use_postal_code='78701',use_country='US',use_region='TX')
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=11,
        idempotency_key='order-retry-key-0001',values=values,timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
        order_id=order['id'],timestamp='t2')
    content=b'PK\x03\x04fictional-issued-word'
    digest=sha256(content).hexdigest()
    agreement=record_generated_candidate(conn,tenant_id=1,buyer_user_id=11,
        order_id=order['id'],quote_id=quote['id'],template_version='Approved-1',
        template_sha256='a'*64,content=content,readback=content,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',
        timestamp='t3')
    args=dict(tenant_id=1,buyer_user_id=11,order_id=order['id'],
        quote_id=quote['id'],agreement_id=agreement['id'],
        expected_agreement_sha256=digest,readback=content,
        consent_text=CONSENT_TEXT_V1,
        typed_name='Jordan Buyer',authority_basis='I am the authorized company officer.',
        idempotency_key='acceptance-key-0001',timestamp='t4')
    return conn, values, args


def test_candidate_cannot_be_accepted_and_exact_issued_version_locks_scope():
    conn, values, args=_setup()
    with pytest.raises(AcceptanceConflict,match='issued agreement'):
        accept_issued_agreement(conn,**args)
    assert conn.execute('SELECT COUNT(*) FROM level1a_acceptances').fetchone()[0]==0
    assert conn.execute('SELECT status FROM level1a_orders').fetchone()[0]=='ReadyForAgreement'
    # Simulates a separately governed exact-version issue. No production route
    # can perform this transition in the current release candidate.
    conn.execute("UPDATE level1a_agreement_versions SET status='Issued'")
    with pytest.raises(AcceptanceConflict,match='Download'):
        accept_issued_agreement(conn,**args)
    record_issued_download(conn,tenant_id=1,buyer_user_id=11,
        order_id=args['order_id'],agreement_id=args['agreement_id'],
        readback=args['readback'],timestamp='t3')
    accepted,retry=accept_issued_agreement(conn,**args)
    assert not retry and accepted['agreement_sha256']==args['expected_agreement_sha256']
    assert accepted['scope_sha256'] and accepted['quote_sha256']
    assert conn.execute('SELECT status FROM level1a_orders').fetchone()[0]=='Accepted'
    assert accept_issued_agreement(conn,**args)[1]
    with pytest.raises(OrderConflict,match='accepted or paid'):
        correct_draft(conn,tenant_id=1,buyer_user_id=11,order_id=args['order_id'],
                      expected_scope_version=1,values=values,timestamp='t5')


def test_cross_member_wrong_bytes_and_retry_mutation_fail_closed():
    conn, _values, args=_setup()
    conn.execute("UPDATE level1a_agreement_versions SET status='Issued'")
    with pytest.raises(AgreementConflict,match='readback'):
        record_issued_download(conn,tenant_id=1,buyer_user_id=11,
            order_id=args['order_id'],agreement_id=args['agreement_id'],
            readback=b'PK\x03\x04changed',timestamp='t3')
    record_issued_download(conn,tenant_id=1,buyer_user_id=11,
        order_id=args['order_id'],agreement_id=args['agreement_id'],
        readback=args['readback'],timestamp='t3')
    with pytest.raises(AcceptanceConflict,match='Member order'):
        accept_issued_agreement(conn,**{**args,'tenant_id':2,'buyer_user_id':22})
    with pytest.raises(AcceptanceConflict,match='differs'):
        accept_issued_agreement(conn,**{**args,'readback':b'PK\x03\x04changed'})
    with pytest.raises(AcceptanceConflict,match='consent'):
        accept_issued_agreement(conn,**{**args,'consent_text':'I agree'})
    assert conn.execute('SELECT COUNT(*) FROM level1a_acceptances').fetchone()[0]==0
    accept_issued_agreement(conn,**args)
    with pytest.raises(AcceptanceConflict,match='different acceptance'):
        accept_issued_agreement(conn,**{**args,'typed_name':'Different Signer'})
    with pytest.raises(AcceptanceConflict,match='already been accepted'):
        accept_issued_agreement(conn,**{**args,'idempotency_key':'another-acceptance-key'})


def test_corrected_scope_invalidates_old_issued_agreement():
    conn, values, args=_setup()
    conn.execute("UPDATE level1a_agreement_versions SET status='Issued'")
    record_issued_download(conn,tenant_id=1,buyer_user_id=11,
        order_id=args['order_id'],agreement_id=args['agreement_id'],
        readback=args['readback'],timestamp='t3')
    correct_draft(conn,tenant_id=1,buyer_user_id=11,order_id=args['order_id'],
                  expected_scope_version=1,
                  values={**values,'unit_name':'River Street daycare'},timestamp='t5')
    with pytest.raises(AcceptanceConflict,match='current scope'):
        accept_issued_agreement(conn,**args)
    assert conn.execute('SELECT COUNT(*) FROM level1a_acceptances').fetchone()[0]==0
