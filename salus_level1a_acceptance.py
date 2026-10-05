"""Exact-version electronic acceptance for an issued Level 1A agreement.

The caller must read the displayed agreement bytes back from governed storage.
This module cannot issue a candidate agreement or authorize payment by itself.
"""

from hashlib import sha256
import re

from salus_level1a_quote import QuoteFacts


CONSENT_TEXT_V1 = (
    'I have read the complete Level 1A agreement, the one covered unit, '
    'the exclusions, and the itemized price. I have authority to approve '
    'this agreement for the Protected Member and consent to electronic records.'
)


ACCEPTANCE_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_acceptances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  quote_id INTEGER NOT NULL,
  agreement_id INTEGER NOT NULL,
  scope_version INTEGER NOT NULL,
  scope_sha256 TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  agreement_sha256 TEXT NOT NULL,
  consent_text_sha256 TEXT NOT NULL,
  typed_name TEXT NOT NULL,
  authority_basis TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  accepted_at TEXT NOT NULL,
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (agreement_id) REFERENCES level1a_agreement_versions(id) ON DELETE RESTRICT,
  UNIQUE (tenant_id,buyer_user_id,idempotency_key),
  UNIQUE (tenant_id,order_id)
);
CREATE INDEX IF NOT EXISTS idx_level1a_acceptance_buyer
  ON level1a_acceptances(tenant_id,buyer_user_id,order_id);
'''


class AcceptanceConflict(ValueError):
    pass


def accept_issued_agreement(conn, *, tenant_id, buyer_user_id, order_id,
                            quote_id, agreement_id, expected_agreement_sha256,
                            readback, consent_text, typed_name, authority_basis,
                            idempotency_key, timestamp):
    """Atomically lock one current order after affirmative exact-byte acceptance.

    The caller owns a transaction and must commit only when this returns. The
    affirmative UI checkbox and authenticated session are checked at the API
    boundary; this ledger independently checks their exact recorded facts.
    """
    if not re.fullmatch(r'[A-Za-z0-9_-]{16,120}', idempotency_key or ''):
        raise AcceptanceConflict('A valid acceptance retry key is required.')
    if not isinstance(readback, bytes) or not readback.startswith(b'PK'):
        raise AcceptanceConflict('The issued agreement could not be read back.')
    if (consent_text != CONSENT_TEXT_V1
            or not isinstance(typed_name, str) or not 2 <= len(typed_name.strip()) <= 200
            or not isinstance(authority_basis, str)
            or not 12 <= len(authority_basis.strip()) <= 1000):
        raise AcceptanceConflict('The electronic consent and authority record is incomplete.')
    if (not re.fullmatch(r'[0-9a-f]{64}', expected_agreement_sha256 or '')
            or sha256(readback).hexdigest() != expected_agreement_sha256):
        raise AcceptanceConflict('The displayed agreement differs from the issued version.')
    order=conn.execute('''SELECT * FROM level1a_orders WHERE id=? AND tenant_id=?
        AND buyer_user_id=?''',(order_id,tenant_id,buyer_user_id)).fetchone()
    quote=conn.execute('''SELECT * FROM level1a_quote_versions WHERE id=? AND tenant_id=?
        AND buyer_user_id=? AND order_id=?''',
        (quote_id,tenant_id,buyer_user_id,order_id)).fetchone()
    agreement=conn.execute('''SELECT * FROM level1a_agreement_versions WHERE id=?
        AND tenant_id=? AND buyer_user_id=? AND order_id=? AND quote_id=?''',
        (agreement_id,tenant_id,buyer_user_id,order_id,quote_id)).fetchone()
    if not order or not quote or not agreement:
        raise AcceptanceConflict('The selected Member order, quote or agreement was not found.')
    if (order['status'] not in ('ReadyForAgreement','Accepted') or
            order['scope_version'] != quote['scope_version'] or
            order['scope_version'] != agreement['scope_version'] or
            order['scope_sha256'] != quote['scope_sha256'] or
            order['scope_sha256'] != agreement['scope_sha256'] or
            quote['quote_sha256'] != agreement['quote_sha256'] or
            agreement['content_sha256'] != expected_agreement_sha256 or
            agreement['status'] != 'Issued' or agreement['origin'] != 'SalusGenerated'):
        raise AcceptanceConflict('The current scope, quote and issued agreement do not match.')
    facts=QuoteFacts(**{key: quote[key] for key in QuoteFacts.__dataclass_fields__})
    if (facts.sha256() != quote['quote_sha256'] or
            facts.total_cents != facts.base_price_cents + facts.tax_cents or
            facts.base_price_cents != 150_000 or facts.currency != 'USD'):
        raise AcceptanceConflict('The issued price no longer matches its recorded facts.')
    download=conn.execute('''SELECT id FROM level1a_agreement_downloads WHERE
        tenant_id=? AND buyer_user_id=? AND order_id=? AND agreement_id=?
        AND content_sha256=? ORDER BY id DESC LIMIT 1''',
        (tenant_id,buyer_user_id,order_id,agreement_id,
         expected_agreement_sha256)).fetchone()
    if not download:
        raise AcceptanceConflict('Download the exact issued agreement before accepting.')
    existing=conn.execute('''SELECT * FROM level1a_acceptances WHERE tenant_id=?
        AND buyer_user_id=? AND idempotency_key=?''',
        (tenant_id,buyer_user_id,idempotency_key)).fetchone()
    consent_hash=sha256(consent_text.encode('utf-8')).hexdigest()
    if existing:
        if (existing['order_id'] != order_id or existing['quote_id'] != quote_id or
                existing['agreement_id'] != agreement_id or
                existing['consent_text_sha256'] != consent_hash or
                existing['typed_name'] != typed_name.strip() or
                existing['authority_basis'] != authority_basis.strip()):
            raise AcceptanceConflict('That retry key belongs to a different acceptance.')
        return dict(existing), True
    if order['status'] != 'ReadyForAgreement':
        raise AcceptanceConflict('This order has already been accepted.')
    locked=conn.execute('''UPDATE level1a_orders SET status='Accepted',updated_at=?
        WHERE id=? AND tenant_id=? AND buyer_user_id=? AND status='ReadyForAgreement'
        AND scope_version=? AND scope_sha256=?''',
        (timestamp,order_id,tenant_id,buyer_user_id,
         quote['scope_version'],quote['scope_sha256']))
    if locked.rowcount != 1:
        raise AcceptanceConflict('The order changed before acceptance.')
    conn.execute('''INSERT INTO level1a_acceptances
        (tenant_id,buyer_user_id,order_id,quote_id,agreement_id,scope_version,
         scope_sha256,quote_sha256,agreement_sha256,consent_text_sha256,
         typed_name,authority_basis,idempotency_key,accepted_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (tenant_id,buyer_user_id,order_id,quote_id,agreement_id,
         order['scope_version'],order['scope_sha256'],quote['quote_sha256'],
         expected_agreement_sha256,consent_hash,typed_name.strip(),
         authority_basis.strip(),idempotency_key,timestamp))
    result=conn.execute('''SELECT * FROM level1a_acceptances WHERE tenant_id=?
        AND buyer_user_id=? AND idempotency_key=?''',
        (tenant_id,buyer_user_id,idempotency_key)).fetchone()
    return dict(result), False
