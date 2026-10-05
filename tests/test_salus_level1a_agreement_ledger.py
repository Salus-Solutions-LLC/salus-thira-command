"""A Word candidate belongs to one current order/quote and exact bytes."""

import sqlite3
from hashlib import sha256

import pytest

from salus_level1a_agreement_ledger import (
    AGREEMENT_TABLE_SQL, AgreementConflict, record_generated_candidate,
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
