import sqlite3

import pytest

from salus_level1a_order_ledger import (
    ORDER_TABLE_SQL, OrderConflict, correct_draft, save_draft,
)


@pytest.fixture
def conn():
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    db.execute('CREATE TABLE tenants (id INTEGER PRIMARY KEY)')
    db.execute('CREATE TABLE users (id INTEGER PRIMARY KEY)')
    db.executemany('INSERT INTO tenants(id) VALUES(?)', [(1,), (2,)])
    db.executemany('INSERT INTO users(id) VALUES(?)', [(11,), (12,)])
    db.executescript(ORDER_TABLE_SQL)
    yield db
    db.close()


def answers(**changes):
    result = dict(buyer_legal_name='Example Care LLC',unit_kind='Site',
                  unit_name='Main daycare',covered_boundary='One building and playground',
                  operating_activity='Child care', exclusions='Other sites',
                  decision_owner_role='Chief executive',notice_email='buyer@example.test',
                  use_country='US',use_region='TX')
    result.update(changes)
    return result


def save(conn, values=None, tenant_id=1, buyer_user_id=11, key='retry-one'):
    return save_draft(conn, tenant_id=tenant_id,buyer_user_id=buyer_user_id,
                      idempotency_key=key,values=values or answers(),
                      timestamp='2026-10-04T23:00:00Z')


def test_retry_is_one_order_and_changed_key_cannot_reuse_old_acceptance(conn):
    first, repeated = save(conn)
    again, idempotent = save(conn)
    assert not repeated and idempotent and first['id'] == again['id']
    assert first['scope_sha256'] == again['scope_sha256']
    with pytest.raises(OrderConflict):
        save(conn, answers(unit_name='Different site'))
    normalized, same = save(conn, answers(unit_name='  Main   daycare  '))
    assert same and normalized['id'] == first['id']


def test_missing_unit_preserves_order_reference_then_correction_changes_digest(conn):
    draft, _ = save(conn, answers(unit_name=''))
    assert draft['status'] == 'NeedsCorrection'
    assert draft['scope_sha256'] == ''
    fixed, same = correct_draft(conn,tenant_id=1,buyer_user_id=11,
        order_id=draft['id'],expected_scope_version=1,values=answers(),
        timestamp='2026-10-04T23:01:00Z')
    assert not same and fixed['id'] == draft['id']
    assert fixed['scope_version'] == 2 and len(fixed['scope_sha256']) == 64
    with pytest.raises(OrderConflict):
        correct_draft(conn,tenant_id=1,buyer_user_id=11,order_id=draft['id'],
            expected_scope_version=1,values=answers(unit_name='Third site'),
            timestamp='2026-10-04T23:02:00Z')


def test_other_member_cannot_read_or_correct_order(conn):
    first, _ = save(conn)
    with pytest.raises(OrderConflict):
        correct_draft(conn,tenant_id=2,buyer_user_id=12,order_id=first['id'],
            expected_scope_version=1,values=answers(),timestamp='2026-10-04T23:01:00Z')


def test_correction_changes_scope_digest_on_same_order(conn):
    first, _ = save(conn)
    changed, _ = correct_draft(conn,tenant_id=1,buyer_user_id=11,
        order_id=first['id'],expected_scope_version=1,
        values=answers(unit_name='Second site'),timestamp='2026-10-04T23:01:00Z')
    assert changed['id'] == first['id']
    assert changed['scope_sha256'] != first['scope_sha256']
