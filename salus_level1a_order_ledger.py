"""Durable, tenant-bound draft orders for the standard Level 1A unit.

An order reference survives incomplete scope answers. This ledger does not
authorize an agreement, payment, report, or file upload.
"""

from salus_level1a_order import Level1AUnit, OrderBoundaryError


ORDER_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  idempotency_key TEXT NOT NULL,
  scope_version INTEGER NOT NULL,
  unit_kind TEXT NOT NULL,
  unit_name TEXT NOT NULL,
  operating_activity TEXT NOT NULL,
  exclusions TEXT NOT NULL,
  use_country TEXT NOT NULL,
  use_region TEXT NOT NULL,
  scope_sha256 TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  UNIQUE (tenant_id,buyer_user_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_level1a_orders_tenant
  ON level1a_orders(tenant_id,buyer_user_id,id);
'''


class OrderConflict(ValueError):
    pass


def _snapshot(values):
    return tuple(values[key] for key in
                 ('unit_kind', 'unit_name', 'operating_activity', 'exclusions',
                  'use_country', 'use_region'))


def _scope(tenant_id, buyer_user_id, scope_version, values):
    try:
        unit = Level1AUnit(tenant_id, buyer_user_id, scope_version=scope_version,
                           **values)
    except OrderBoundaryError:
        return 'NeedsCorrection', '', values
    return 'ReadyForAgreement', unit.digest(), {
        'unit_kind': unit.unit_kind,
        'unit_name': unit.unit_name,
        'operating_activity': unit.operating_activity,
        'exclusions': unit.exclusions,
        'use_country': unit.use_country,
        'use_region': unit.use_region,
    }


def save_draft(conn, *, tenant_id, buyer_user_id, idempotency_key, values, timestamp):
    if not idempotency_key or len(idempotency_key) > 120:
        raise OrderConflict('A bounded order retry key is required.')
    values = {key: values[key] for key in
              ('unit_kind', 'unit_name', 'operating_activity', 'exclusions',
               'use_country', 'use_region')}
    if any(not isinstance(value, str) or len(value) > 500 for value in values.values()):
        raise OrderConflict('Order answers must be text of at most 500 characters.')
    status, digest, normalized = _scope(tenant_id, buyer_user_id, 1, values)
    existing = conn.execute('''SELECT * FROM level1a_orders
        WHERE tenant_id=? AND buyer_user_id=? AND idempotency_key=?''',
        (tenant_id, buyer_user_id, idempotency_key)).fetchone()
    if existing:
        if _snapshot(existing) != _snapshot(normalized):
            raise OrderConflict('That retry key belongs to a different order. Correct the saved order instead.')
        return dict(existing), True
    conn.execute('''INSERT INTO level1a_orders
        (tenant_id,buyer_user_id,idempotency_key,scope_version,unit_kind,unit_name,
         operating_activity,exclusions,use_country,use_region,scope_sha256,status,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(tenant_id,buyer_user_id,idempotency_key)
        DO NOTHING''', (tenant_id,buyer_user_id,idempotency_key,1,
        *_snapshot(normalized),digest,status,timestamp,timestamp))
    row = conn.execute('''SELECT * FROM level1a_orders
        WHERE tenant_id=? AND buyer_user_id=? AND idempotency_key=?''',
        (tenant_id,buyer_user_id,idempotency_key)).fetchone()
    if _snapshot(row) != _snapshot(normalized):
        raise OrderConflict('A concurrent order used that retry key with different answers.')
    return dict(row), False


def correct_draft(conn, *, tenant_id, buyer_user_id, order_id,
                  expected_scope_version, values, timestamp):
    row = conn.execute('''SELECT * FROM level1a_orders
        WHERE id=? AND tenant_id=? AND buyer_user_id=?''',
        (order_id,tenant_id,buyer_user_id)).fetchone()
    if not row:
        raise OrderConflict('Order not found for this Protected Member buyer.')
    if row['status'] not in ('NeedsCorrection','ReadyForAgreement'):
        raise OrderConflict('An accepted or paid order requires a new amendment.')
    if row['scope_version'] != expected_scope_version:
        raise OrderConflict('This order changed. Refresh before correcting it.')
    values = {key: values[key] for key in
              ('unit_kind', 'unit_name', 'operating_activity', 'exclusions',
               'use_country', 'use_region')}
    if any(not isinstance(value, str) or len(value) > 500 for value in values.values()):
        raise OrderConflict('Order answers must be text of at most 500 characters.')
    version = expected_scope_version + 1
    status, digest, normalized = _scope(tenant_id,buyer_user_id,version,values)
    if _snapshot(row) == _snapshot(normalized):
        return dict(row), True
    result = conn.execute('''UPDATE level1a_orders SET scope_version=?,unit_kind=?,
        unit_name=?,operating_activity=?,exclusions=?,use_country=?,use_region=?,
        scope_sha256=?,status=?,updated_at=?
        WHERE id=? AND tenant_id=? AND buyer_user_id=? AND scope_version=?
          AND status IN ('NeedsCorrection','ReadyForAgreement')''',
        (version,*_snapshot(normalized),digest,status,timestamp,
         order_id,tenant_id,buyer_user_id,expected_scope_version))
    if result.rowcount != 1:
        raise OrderConflict('This order changed. Refresh before correcting it.')
    return dict(conn.execute('SELECT * FROM level1a_orders WHERE id=?',(order_id,)).fetchone()), False
