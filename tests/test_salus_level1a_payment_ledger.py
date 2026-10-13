"""A signed, retrieved paid Session is the only receipt authority."""

import sqlite3
from hashlib import sha256

import pytest

from salus_level1a_acceptance import (ACCEPTANCE_TABLE_SQL,CONSENT_TEXT_V1,
                                      accept_issued_agreement)
from salus_level1a_agreement_ledger import (AGREEMENT_TABLE_SQL,
    record_generated_candidate,record_issued_download)
from salus_level1a_order_ledger import ORDER_TABLE_SQL,save_draft
from salus_level1a_quote import QUOTE_TABLE_SQL,quote_for_order
from salus_level1a_payment_ledger import (LEVEL1A_PAYMENT_SQL,
    binding_for_accepted_order,record_level1a_session,record_level1a_paid,
    hold_level1a_payment,verified_level1a_receipt,
    record_level1a_receipt_document,issued_level1a_receipt)
from salus_level1a_receipt import render_level1a_receipt
from salus_stripe_checkout import CheckoutVerificationError


def _accepted():
    conn=sqlite3.connect(':memory:');conn.row_factory=sqlite3.Row
    conn.executescript('''CREATE TABLE tenants(id INTEGER PRIMARY KEY);
        CREATE TABLE users(id INTEGER PRIMARY KEY);
        INSERT INTO tenants VALUES(1); INSERT INTO users VALUES(2);''')
    for sql in (ORDER_TABLE_SQL,QUOTE_TABLE_SQL,AGREEMENT_TABLE_SQL,
                ACCEPTANCE_TABLE_SQL,LEVEL1A_PAYMENT_SQL):
        conn.executescript(sql)
    values=dict(buyer_legal_name='Example Care LLC',unit_kind='Site',
        unit_name='Oak Street site',covered_boundary='One building',
        operating_activity='Child care',exclusions='Other locations',
        decision_owner_role='Chief executive',notice_email='buyer@example.test',
        service_use_address='100 Oak Street, Austin, Texas',
        service_use_postal_code='78701',use_country='US',use_region='TX')
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=2,
        idempotency_key='accepted-order-001',values=values,timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],timestamp='t2')
    word=b'PK\x03\x04fictional-word';digest=sha256(word).hexdigest()
    agreement=record_generated_candidate(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],quote_id=quote['id'],template_version='fictional',
        template_sha256='a'*64,content=word,readback=word,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',
        timestamp='t3')
    conn.execute("UPDATE level1a_agreement_versions SET status='Issued' WHERE id=?",
                 (agreement['id'],))
    record_issued_download(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],agreement_id=agreement['id'],
        readback=word,timestamp='t4')
    accept_issued_agreement(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],quote_id=quote['id'],agreement_id=agreement['id'],
        expected_agreement_sha256=digest,readback=word,
        consent_text=CONSENT_TEXT_V1,typed_name='Jane Example',
        authority_basis='Chief executive with contracting authority',
        idempotency_key='accept-order-00001',timestamp='t5')
    return conn,binding_for_accepted_order(conn,tenant_id=1,buyer_user_id=2,
                                           order_id=order['id'])


def _paid(binding):
    return {'id':'cs_test_fictional12345','object':'checkout.session',
        'status':'complete','payment_status':'paid','mode':'payment',
        'livemode':False,'amount_subtotal':150_000,'amount_total':150_000,
        'currency':'usd','total_details':{'amount_tax':0},
        'client_reference_id':str(binding.acceptance_id),
        'metadata':binding.metadata(),'payment_intent':'pi_fictional'}


def test_verified_payment_produces_one_receipt_and_refund_holds_it():
    conn,binding=_accepted()
    saved=record_level1a_session(conn,binding,1,'cs_test_fictional12345',
        'https://checkout.stripe.com/c/pay/fictional','t6')
    assert saved['status']=='Pending'
    assert record_level1a_session(conn,binding,1,'cs_test_fictional12345',
        'https://checkout.stripe.com/c/pay/fictional','t6')['id']==saved['id']
    paid=record_level1a_paid(conn,binding,_paid(binding),'evt_paid_1',
        'checkout.session.completed','t7',False)
    assert paid['status']=='Paid' and len(paid['receipt_sha256'])==64
    assert verified_level1a_receipt(conn,binding)['id']==saved['id']
    assert record_level1a_paid(conn,binding,_paid(binding),'evt_paid_1',
        'checkout.session.completed','t8',False)['receipt_sha256']==paid['receipt_sha256']
    held=hold_level1a_payment(conn,'pi_fictional','evt_refund_1',
        'charge.refunded','t9')
    assert held['status']=='Held' and verified_level1a_receipt(conn,binding) is None


def test_wrong_paid_total_never_issues_receipt_and_early_hold_blocks_payment():
    conn,binding=_accepted()
    record_level1a_session(conn,binding,1,'cs_test_fictional12345',
        'https://checkout.stripe.com/c/pay/fictional','t6')
    with pytest.raises(CheckoutVerificationError,match='subtotal'):
        record_level1a_paid(conn,binding,_paid(binding)|{'amount_total':149_999},
                            'evt_wrong_1','checkout.session.completed','t7',False)
    assert verified_level1a_receipt(conn,binding) is None
    assert hold_level1a_payment(conn,'pi_fictional','evt_refund_early',
        'charge.refunded','t8') is None
    held=record_level1a_paid(conn,binding,_paid(binding),'evt_paid_2',
        'checkout.session.completed','t9',False)
    assert held['status']=='Held' and verified_level1a_receipt(conn,binding) is None


def test_exact_one_page_receipt_bytes_are_immutable_and_member_bound():
    conn,binding=_accepted()
    record_level1a_session(conn,binding,1,'cs_test_fictional12345',
        'https://checkout.stripe.com/c/pay/fictional','t6')
    paid=record_level1a_paid(conn,binding,_paid(binding),'evt_paid_1',
        'checkout.session.completed','2026-10-05T13:00:00Z',False)
    order=conn.execute('SELECT * FROM level1a_orders WHERE id=?',
                       (binding.order_id,)).fetchone()
    quote=conn.execute('SELECT * FROM level1a_quote_versions WHERE id=?',
                       (binding.quote_id,)).fetchone()
    agreement=conn.execute('SELECT * FROM level1a_agreement_versions WHERE id=1').fetchone()
    content=render_level1a_receipt(order,quote,agreement,paid)
    assert b'Page 1 of 1' in content and b'05 October 2026 at 13:00 UTC' in content
    assert b'STRIPE SANDBOX' in content and b'NO LIVE CHARGE' in content
    assert b'Test amount' in content and b'Sandbox payment verified' in content
    assert b'Total paid' not in content
    assert b'Fictional Daycare LLC' not in content
    assert b'Example Care LLC' in content
    digest=sha256(content).hexdigest()
    key=f'level1a/1/{binding.order_id}/receipts/{digest}.html'
    stored=record_level1a_receipt_document(conn,binding,paid['id'],content,key,content)
    assert stored['receipt_document_sha256']==digest
    assert issued_level1a_receipt(conn,binding,content)['id']==paid['id']
    with pytest.raises(CheckoutVerificationError,match='stored receipt'):
        issued_level1a_receipt(conn,binding,content+b'altered')
    with pytest.raises(CheckoutVerificationError,match='immutable'):
        record_level1a_receipt_document(conn,binding,paid['id'],
            content+b'changed',
            f'level1a/1/{binding.order_id}/receipts/{sha256(content+b"changed").hexdigest()}.html',
            content+b'changed')
