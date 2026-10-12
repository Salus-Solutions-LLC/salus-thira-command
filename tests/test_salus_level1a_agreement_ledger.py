"""A Word candidate belongs to one current order/quote and exact bytes."""

import sqlite3
from hashlib import sha256
from io import BytesIO

import pytest
from docx import Document

from salus_level1a_agreement_ledger import (
    AGREEMENT_TABLE_SQL, APPROVED_TEMPLATE_SHA256, APPROVED_TEMPLATE_VERSION,
    AgreementConflict, issue_generated_agreement,
    record_generated_candidate,
)
from salus_level1a_order_ledger import ORDER_TABLE_SQL, save_draft, correct_draft
from salus_level1a_quote import QUOTE_TABLE_SQL, quote_for_order


def _database():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.executescript('''CREATE TABLE tenants(id INTEGER PRIMARY KEY);
        CREATE TABLE users(id INTEGER PRIMARY KEY);
        INSERT INTO tenants(id) VALUES(1);
        INSERT INTO users(id) VALUES(2);''')
    for script in (ORDER_TABLE_SQL,QUOTE_TABLE_SQL,AGREEMENT_TABLE_SQL):
        conn.executescript(script)
    return conn


def _values(unit_name='Oak Street daycare'):
    return dict(buyer_legal_name='Example Care LLC',unit_kind='Site',
        unit_name=unit_name,covered_boundary='One building and playground',
        operating_activity='Child care',exclusions='Other locations',
        decision_owner_role='Chief executive',notice_email='buyer@example.test',
        service_use_address='100 Oak Street, Austin, Texas',
        service_use_postal_code='78701',use_country='US',use_region='TX')


def test_current_quote_and_storage_readback_bind_one_candidate():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=2,
        idempotency_key='agreement-order-0001',values=_values(),timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=2,
                          order_id=order['id'],timestamp='t2')
    content=b'PK\x03\x04fictional'
    digest=sha256(content).hexdigest()
    args=dict(tenant_id=1,buyer_user_id=2,order_id=order['id'],quote_id=quote['id'],
        template_version='Candidate-Rev9',template_sha256='a'*64,
        content=content,readback=content,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',timestamp='t3')
    stored=record_generated_candidate(conn,**args)
    assert stored['status']=='Candidate' and stored['origin']=='SalusGenerated'
    assert record_generated_candidate(conn,**args)['id']==stored['id']
    with pytest.raises(AgreementConflict,match='saved agreement differs'):
        record_generated_candidate(conn,**{**args,'readback':b'PK\x03\x04different'})
    with pytest.raises(AgreementConflict,match='outside its order'):
        record_generated_candidate(conn,**{**args,'stored_name':'level1a/99/1/1/sample.docx'})
    correct_draft(conn,tenant_id=1,buyer_user_id=2,order_id=order['id'],
                  expected_scope_version=1,values=_values('River Street daycare'),
                  timestamp='t4')
    with pytest.raises(AgreementConflict,match='scope or quote changed'):
        record_generated_candidate(conn,**args)


def _issued_word(order, quote, *, draft=False):
    doc=Document()
    for line in (
        'Level 1A Access Statement of Work',
        'Version and effective date  Standard terms revision 11, 9 October 2026; '
        'effective only on electronic Member acceptance of the completed issued version',
        f'Protected Member legal name  {order["buyer_legal_name"]}',
        f'Primary operating activity  {order["operating_activity"]}',
        f'Covered boundary  {order["covered_boundary"]}',
        f'Express exclusions  {order["exclusions"]}',
        f'Order and notices  L1A-{order["id"]} / Q{quote["id"]} / '
        f'v{order["scope_version"]}; {order["notice_email"]}',
        f'Applicable tax and total  $0.00 tax; $1,500.00 total USD; '
        f'approved remote Level 1A assessment tax decision '
        f'({quote["tax_decision_reference"]})',
        'Review Draft' if draft else 'Salus Confidential',
    ):
        doc.add_paragraph(line)
    buffer=BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def test_issue_requires_approved_template_complete_current_word_and_quote():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=2,
        idempotency_key='agreement-order-issue',values=_values(),timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=2,
                          order_id=order['id'],timestamp='t2')
    word=_issued_word(order,quote)
    digest=sha256(word).hexdigest()
    candidate=record_generated_candidate(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],quote_id=quote['id'],template_version=APPROVED_TEMPLATE_VERSION,
        template_sha256=APPROVED_TEMPLATE_SHA256,content=word,readback=word,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',
        timestamp='t3')
    params=dict(tenant_id=1,buyer_user_id=2,order_id=order['id'],
        quote_id=quote['id'],agreement_id=candidate['id'],
        approved_template_sha256=APPROVED_TEMPLATE_SHA256,readback=word,timestamp='t4')
    with pytest.raises(AgreementConflict,match='exact approved'):
        issue_generated_agreement(conn,**{**params,'approved_template_sha256':'b'*64})
    with pytest.raises(AgreementConflict,match='stored agreement bytes'):
        issue_generated_agreement(conn,**{**params,'readback':word+b'altered'})
    issued=issue_generated_agreement(conn,**params)
    assert issued['status']=='Issued' and issued['issued_at']=='t4'
    with pytest.raises(AgreementConflict,match='current approved'):
        issue_generated_agreement(conn,**params)


def test_issue_rejects_draft_word_even_with_matching_saved_hash():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=2,
        idempotency_key='agreement-order-draft',values=_values(),timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=2,
                          order_id=order['id'],timestamp='t2')
    word=_issued_word(order,quote,draft=True)
    digest=sha256(word).hexdigest()
    candidate=record_generated_candidate(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],quote_id=quote['id'],template_version=APPROVED_TEMPLATE_VERSION,
        template_sha256=APPROVED_TEMPLATE_SHA256,content=word,readback=word,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',
        timestamp='t3')
    with pytest.raises(AgreementConflict,match='drafting or incomplete'):
        issue_generated_agreement(conn,tenant_id=1,buyer_user_id=2,
            order_id=order['id'],quote_id=quote['id'],agreement_id=candidate['id'],
            approved_template_sha256=APPROVED_TEMPLATE_SHA256,readback=word,timestamp='t4')


def test_issue_rejects_rev11_candidate_label_even_without_review_draft():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=2,
        idempotency_key='agreement-order-rev11-candidate',values=_values(),timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=2,
                          order_id=order['id'],timestamp='t2')
    word=_issued_word(order,quote)
    doc=Document(BytesIO(word))
    doc.add_paragraph('Candidate revision for review 9 October 2026')
    stream=BytesIO(); doc.save(stream); word=stream.getvalue()
    digest=sha256(word).hexdigest()
    candidate=record_generated_candidate(conn,tenant_id=1,buyer_user_id=2,
        order_id=order['id'],quote_id=quote['id'],template_version=APPROVED_TEMPLATE_VERSION,
        template_sha256=APPROVED_TEMPLATE_SHA256,content=word,readback=word,
        stored_name=f'level1a/1/{order["id"]}/{quote["id"]}/{digest}.docx',timestamp='t3')
    with pytest.raises(AgreementConflict,match='drafting or incomplete'):
        issue_generated_agreement(conn,tenant_id=1,buyer_user_id=2,
            order_id=order['id'],quote_id=quote['id'],agreement_id=candidate['id'],
            approved_template_sha256=APPROVED_TEMPLATE_SHA256,readback=word,timestamp='t4')
