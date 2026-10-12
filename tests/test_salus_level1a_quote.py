"""A corrected one-unit scope needs a new, exact priced quote."""

import sqlite3

import pytest

from salus_level1a_order_ledger import ORDER_TABLE_SQL, save_draft, correct_draft
from salus_level1a_quote import (QUOTE_TABLE_SQL, QuoteFacts, QuoteUnavailable,
                                 _unit_from_order, quote_for_order)


def _values(*, region='TX', unit_name='Oak Street daycare'):
    return {'buyer_legal_name':'Example Care LLC','unit_kind':'Site',
            'unit_name':unit_name,'covered_boundary':'Building and playground',
            'operating_activity':'Daycare','exclusions':'Other sites',
            'decision_owner_role':'Chief executive',
            'notice_email':'buyer@example.test',
            'service_use_address':'100 Oak Street, Austin, Texas',
            'service_use_postal_code':'78701','use_country':'US',
            'use_region':region}


def _database():
    conn=sqlite3.connect(':memory:')
    conn.row_factory=sqlite3.Row
    conn.executescript('''CREATE TABLE tenants(id INTEGER PRIMARY KEY);
        CREATE TABLE users(id INTEGER PRIMARY KEY);''')
    conn.execute('INSERT INTO tenants(id) VALUES(1)')
    conn.execute('INSERT INTO tenants(id) VALUES(2)')
    conn.execute('INSERT INTO users(id) VALUES(11)')
    conn.execute('INSERT INTO users(id) VALUES(22)')
    conn.executescript(ORDER_TABLE_SQL)
    conn.executescript(QUOTE_TABLE_SQL)
    return conn


def test_quote_is_immutable_and_new_scope_needs_new_price():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=11,
        idempotency_key='unique-order-0001',values=_values(),timestamp='t1')
    first=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
                          order_id=order['id'],timestamp='t2')
    again=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
                          order_id=order['id'],timestamp='t3')
    assert first['id']==again['id']
    assert (first['base_price_cents'],first['tax_cents'],first['total_cents'])==(150000,0,150000)
    assert first['tax_decision_reference']=='SAL-D107'
    with pytest.raises(QuoteUnavailable):
        quote_for_order(conn,tenant_id=2,buyer_user_id=22,
                        order_id=order['id'],timestamp='t4')
    corrected,_=correct_draft(conn,tenant_id=1,buyer_user_id=11,
        order_id=order['id'],expected_scope_version=1,
        values=_values(unit_name='River Street daycare'),timestamp='t5')
    second=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
                           order_id=order['id'],timestamp='t6')
    assert corrected['scope_version']==2
    assert second['id']!=first['id']
    assert second['quote_sha256']!=first['quote_sha256']
    assert conn.execute('SELECT COUNT(*) FROM level1a_quote_versions').fetchone()[0]==2


def test_other_us_state_keeps_fixed_total_and_exact_tax_basis():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=11,
        idempotency_key='unique-order-0002',values=_values(region='OK'),timestamp='t1')
    quote=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
                          order_id=order['id'],timestamp='t2')
    assert (quote['base_price_cents'],quote['tax_cents'],quote['total_cents'])==(150000,0,150000)
    assert (quote['tax_rule_id'],quote['tax_decision_reference'])==('REMOTE-LEVEL1A-US-V1','SAL-D107')
    assert conn.execute('SELECT COUNT(*) FROM level1a_quote_versions').fetchone()[0]==1


def test_other_country_remains_unavailable():
    conn=_database()
    values=_values(region='ON') | {'use_country':'CA'}
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=11,
        idempotency_key='unique-order-0003',values=values,timestamp='t1')
    with pytest.raises(QuoteUnavailable,match='tax determination'):
        quote_for_order(conn,tenant_id=1,buyer_user_id=11,
                        order_id=order['id'],timestamp='t2')
    assert conn.execute('SELECT COUNT(*) FROM level1a_quote_versions').fetchone()[0]==0


def test_existing_immutable_texas_rule_quote_remains_readable():
    conn=_database()
    order,_=save_draft(conn,tenant_id=1,buyer_user_id=11,
        idempotency_key='unique-order-legacy',values=_values(region='OK'),timestamp='t1')
    unit=_unit_from_order(order)
    facts=QuoteFacts(1,11,order['id'],1,unit.digest(),
        'TX-PERFORMED-LEVEL1A-V1','SAL-D106','TX',150000,0,150000,'USD')
    conn.execute('''INSERT INTO level1a_quote_versions
        (tenant_id,buyer_user_id,order_id,scope_version,scope_sha256,
         tax_rule_id,tax_decision_reference,tax_jurisdiction,
         base_price_cents,tax_cents,total_cents,currency,quote_sha256,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (facts.tenant_id,facts.buyer_user_id,facts.order_id,facts.scope_version,
         facts.scope_sha256,facts.tax_rule_id,facts.tax_decision_reference,
         facts.tax_jurisdiction,facts.base_price_cents,facts.tax_cents,
         facts.total_cents,facts.currency,facts.sha256(),'t2'))
    old=quote_for_order(conn,tenant_id=1,buyer_user_id=11,
        order_id=order['id'],timestamp='t3')
    assert old['quote_sha256']==facts.sha256()
    assert old['tax_rule_id']=='TX-PERFORMED-LEVEL1A-V1'
    assert conn.execute('SELECT COUNT(*) FROM level1a_quote_versions').fetchone()[0]==1
