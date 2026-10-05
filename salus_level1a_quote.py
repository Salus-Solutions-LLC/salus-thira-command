"""Immutable price facts for one standard Level 1A Access order version.

The only automatic tax decision in this module is Salus's recorded Texas
standard-consulting determination. An unknown location never becomes zero tax.
"""

from dataclasses import dataclass
from hashlib import sha256
import json

from salus_level1a_order import (ApprovedTaxDecision, BASE_PRICE_CENTS,
                                 Level1AUnit, TaxDecisionError)


QUOTE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_quote_versions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  scope_version INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  tax_rule_id TEXT NOT NULL,
  tax_decision_reference TEXT NOT NULL,
  tax_jurisdiction TEXT NOT NULL,
  base_price_cents INTEGER NOT NULL,
  tax_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  UNIQUE (tenant_id,order_id,scope_version)
);
CREATE INDEX IF NOT EXISTS idx_level1a_quotes_buyer
  ON level1a_quote_versions(tenant_id,buyer_user_id,order_id,id);
'''


class QuoteUnavailable(ValueError):
    """The order cannot yet be shown a payable total."""


@dataclass(frozen=True)
class QuoteFacts:
    tenant_id: int
    buyer_user_id: int
    order_id: int
    scope_version: int
    scope_sha256: str
    tax_rule_id: str
    tax_decision_reference: str
    tax_jurisdiction: str
    base_price_cents: int
    tax_cents: int
    total_cents: int
    currency: str

    def sha256(self) -> str:
        payload = json.dumps(self.__dict__, sort_keys=True, separators=(',', ':'))
        return sha256(payload.encode('utf-8')).hexdigest()


def _unit_from_order(row):
    return Level1AUnit(
        tenant_id=row['tenant_id'], buyer_user_id=row['buyer_user_id'],
        buyer_legal_name=row['buyer_legal_name'], unit_kind=row['unit_kind'],
        unit_name=row['unit_name'], covered_boundary=row['covered_boundary'],
        operating_activity=row['operating_activity'], exclusions=row['exclusions'],
        decision_owner_role=row['decision_owner_role'], notice_email=row['notice_email'],
        use_country=row['use_country'], use_region=row['use_region'],
        scope_version=row['scope_version'])


def quote_for_order(conn, *, tenant_id, buyer_user_id, order_id, timestamp):
    """Return the current quote, or make one exact immutable version."""
    order = conn.execute('''SELECT * FROM level1a_orders
        WHERE id=? AND tenant_id=? AND buyer_user_id=?''',
        (order_id, tenant_id, buyer_user_id)).fetchone()
    if not order:
        raise QuoteUnavailable('Order not found for this Protected Member buyer.')
    if order['status'] != 'ReadyForAgreement':
        raise QuoteUnavailable('Complete the selected unit before reviewing a price.')
    unit = _unit_from_order(order)
    if unit.digest() != order['scope_sha256']:
        raise QuoteUnavailable('The saved scope needs reconciliation before pricing.')
    if (unit.use_country, unit.use_region) != ('US', 'TX'):
        raise QuoteUnavailable('A verified tax calculation for this service-use location is pending.')
    tax = ApprovedTaxDecision(unit.digest(), 'TX-STANDARD-CONSULTING-V1',
                              'TX', 0, 'SAL-D099')
    try:
        total = tax.total_cents(unit)
    except TaxDecisionError as exc:
        raise QuoteUnavailable('The tax determination needs reconciliation.') from exc
    facts = QuoteFacts(tenant_id, buyer_user_id, order_id,
                       unit.scope_version, unit.digest(), tax.rule_id,
                       tax.decision_reference, tax.jurisdiction,
                       BASE_PRICE_CENTS, tax.tax_cents, total, 'USD')
    digest = facts.sha256()
    conn.execute('''INSERT INTO level1a_quote_versions
        (tenant_id,buyer_user_id,order_id,scope_version,scope_sha256,
         tax_rule_id,tax_decision_reference,tax_jurisdiction,
         base_price_cents,tax_cents,total_cents,currency,quote_sha256,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(tenant_id,order_id,scope_version) DO NOTHING''',
        (tenant_id,buyer_user_id,order_id,unit.scope_version,unit.digest(),
         tax.rule_id,tax.decision_reference,tax.jurisdiction,
         BASE_PRICE_CENTS,tax.tax_cents,total,'USD',digest,timestamp))
    row = conn.execute('''SELECT * FROM level1a_quote_versions
        WHERE tenant_id=? AND buyer_user_id=? AND order_id=? AND scope_version=?''',
        (tenant_id,buyer_user_id,order_id,unit.scope_version)).fetchone()
    if not row or row['quote_sha256'] != digest:
        raise QuoteUnavailable('The current price record changed; refresh the order.')
    return dict(row)
