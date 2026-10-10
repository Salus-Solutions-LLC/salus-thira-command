"""Tenant-bound Level 1A Stripe decisions and one immutable receipt identity."""

from hashlib import sha256
import json

from salus_level1a_checkout import (Level1ACheckoutBinding,
                                    verify_level1a_paid_session)
from salus_level1a_order import (ApprovedTaxDecision, OrderBoundaryError,
                                 TaxDecisionError)
from salus_level1a_quote import QuoteFacts, _unit_from_order
from salus_stripe_checkout import CheckoutVerificationError


LEVEL1A_PAYMENT_SQL = '''
CREATE TABLE IF NOT EXISTS level1a_checkout_sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tenant_id INTEGER NOT NULL,
  buyer_user_id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  quote_id INTEGER NOT NULL,
  acceptance_id INTEGER NOT NULL,
  attempt_no INTEGER NOT NULL,
  stripe_session_id TEXT NOT NULL UNIQUE,
  checkout_url TEXT NOT NULL,
  scope_sha256 TEXT NOT NULL,
  quote_sha256 TEXT NOT NULL,
  agreement_sha256 TEXT NOT NULL,
  base_price_cents INTEGER NOT NULL,
  tax_cents INTEGER NOT NULL,
  amount_cents INTEGER NOT NULL,
  currency TEXT NOT NULL,
  status TEXT NOT NULL,
  payment_intent_id TEXT NOT NULL DEFAULT '',
  receipt_sha256 TEXT NOT NULL DEFAULT '',
  receipt_document_sha256 TEXT NOT NULL DEFAULT '',
  receipt_stored_name TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  paid_at TEXT NOT NULL DEFAULT '',
  FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
  FOREIGN KEY (buyer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES level1a_orders(id) ON DELETE RESTRICT,
  FOREIGN KEY (quote_id) REFERENCES level1a_quote_versions(id) ON DELETE RESTRICT,
  FOREIGN KEY (acceptance_id) REFERENCES level1a_acceptances(id) ON DELETE RESTRICT,
  UNIQUE(acceptance_id,attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_level1a_checkout_order
  ON level1a_checkout_sessions(tenant_id,buyer_user_id,order_id,acceptance_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_level1a_payment_intent
  ON level1a_checkout_sessions(payment_intent_id) WHERE payment_intent_id<>'';
CREATE TABLE IF NOT EXISTS level1a_payment_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  stripe_event_id TEXT NOT NULL UNIQUE,
  checkout_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  outcome TEXT NOT NULL,
  processed_at TEXT NOT NULL,
  FOREIGN KEY (checkout_id) REFERENCES level1a_checkout_sessions(id) ON DELETE RESTRICT
);
CREATE TABLE IF NOT EXISTS level1a_payment_holds (
  stripe_event_id TEXT NOT NULL PRIMARY KEY,
  payment_intent_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_level1a_hold_intent
  ON level1a_payment_holds(payment_intent_id);
'''


def binding_for_accepted_order(conn, *, tenant_id, buyer_user_id, order_id):
    order=conn.execute('''SELECT * FROM level1a_orders WHERE id=? AND tenant_id=?
        AND buyer_user_id=?''',(order_id,tenant_id,buyer_user_id)).fetchone()
    accepted=conn.execute('''SELECT * FROM level1a_acceptances WHERE order_id=?
        AND tenant_id=? AND buyer_user_id=?''',
        (order_id,tenant_id,buyer_user_id)).fetchone()
    if not order or not accepted or order['status']!='Accepted':
        raise CheckoutVerificationError('No current accepted Level 1A order exists.')
    quote=conn.execute('''SELECT * FROM level1a_quote_versions WHERE id=?
        AND tenant_id=? AND buyer_user_id=? AND order_id=?''',
        (accepted['quote_id'],tenant_id,buyer_user_id,order_id)).fetchone()
    agreement=conn.execute('''SELECT * FROM level1a_agreement_versions WHERE id=?
        AND tenant_id=? AND buyer_user_id=? AND order_id=?''',
        (accepted['agreement_id'],tenant_id,buyer_user_id,order_id)).fetchone()
    if not quote or not agreement or agreement['status']!='Issued':
        raise CheckoutVerificationError('The accepted quote or issued agreement is missing.')
    facts=QuoteFacts(**{key:quote[key] for key in QuoteFacts.__dataclass_fields__})
    tax=ApprovedTaxDecision(quote['scope_sha256'],quote['tax_rule_id'],
        quote['tax_jurisdiction'],quote['tax_cents'],quote['tax_decision_reference'])
    try:
        approved_total=tax.total_cents(_unit_from_order(order))
    except (OrderBoundaryError,TaxDecisionError) as exc:
        raise CheckoutVerificationError('The accepted tax decision is invalid.') from exc
    if (facts.sha256()!=quote['quote_sha256'] or
            order['scope_version']!=accepted['scope_version'] or
            order['scope_sha256']!=accepted['scope_sha256'] or
            quote['scope_sha256']!=accepted['scope_sha256'] or
            quote['quote_sha256']!=accepted['quote_sha256'] or
            agreement['content_sha256']!=accepted['agreement_sha256'] or
            agreement['quote_id']!=quote['id'] or
            accepted['agreement_id']!=agreement['id'] or
            quote['tax_rule_id'] not in ('TX-STANDARD-CONSULTING-V1',
                                         'TX-PERFORMED-LEVEL1A-V1') or
            quote['total_cents']!=approved_total):
        raise CheckoutVerificationError('The accepted scope, quote or tax decision changed.')
    return Level1ACheckoutBinding(tenant_id,buyer_user_id,order_id,quote['id'],
        accepted['id'],accepted['scope_sha256'],accepted['quote_sha256'],
        accepted['agreement_sha256'],quote['base_price_cents'],
        quote['tax_cents'],quote['total_cents'],quote['currency'].lower())


def _same(row,binding):
    return all(row[key]==value for key,value in (
        ('tenant_id',binding.tenant_id),('buyer_user_id',binding.buyer_user_id),
        ('order_id',binding.order_id),('quote_id',binding.quote_id),
        ('acceptance_id',binding.acceptance_id),
        ('scope_sha256',binding.scope_sha256),
        ('quote_sha256',binding.quote_sha256),
        ('agreement_sha256',binding.agreement_sha256),
        ('base_price_cents',binding.base_price_cents),
        ('tax_cents',binding.tax_cents),('amount_cents',binding.amount_cents),
        ('currency',binding.currency)))


def record_level1a_session(conn,binding,attempt_no,session_id,checkout_url,timestamp):
    if (type(attempt_no) is not int or not 1<=attempt_no<=20 or
            not isinstance(session_id,str) or not session_id.startswith('cs_') or
            not isinstance(checkout_url,str) or
            not checkout_url.startswith('https://checkout.stripe.com/')):
        raise CheckoutVerificationError('The returned Checkout Session is invalid.')
    previous=conn.execute('''SELECT * FROM level1a_checkout_sessions WHERE
        acceptance_id=? AND attempt_no=?''',
        (binding.acceptance_id,attempt_no)).fetchone()
    if previous:
        if not _same(previous,binding) or previous['stripe_session_id']!=session_id:
            raise CheckoutVerificationError('This attempt belongs to different terms.')
        return dict(previous)
    cur=conn.execute('''INSERT INTO level1a_checkout_sessions
        (tenant_id,buyer_user_id,order_id,quote_id,acceptance_id,attempt_no,
         stripe_session_id,checkout_url,scope_sha256,quote_sha256,agreement_sha256,
         base_price_cents,tax_cents,amount_cents,currency,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (binding.tenant_id,binding.buyer_user_id,binding.order_id,binding.quote_id,
         binding.acceptance_id,attempt_no,session_id,checkout_url,
         binding.scope_sha256,binding.quote_sha256,binding.agreement_sha256,
         binding.base_price_cents,binding.tax_cents,binding.amount_cents,
         binding.currency,'Pending',timestamp))
    return dict(conn.execute('SELECT * FROM level1a_checkout_sessions WHERE id=?',
                             (cur.lastrowid,)).fetchone())


def _receipt_digest(row,payment_intent_id,paid_at):
    fields={key:row[key] for key in
        ('tenant_id','buyer_user_id','order_id','quote_id','acceptance_id',
         'stripe_session_id','scope_sha256','quote_sha256','agreement_sha256',
         'base_price_cents','tax_cents','amount_cents','currency')}
    fields.update(payment_intent_id=payment_intent_id,paid_at=paid_at)
    return sha256(json.dumps(fields,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def record_level1a_paid(conn,binding,session,event_id,event_type,timestamp,
                        expected_livemode):
    if (not isinstance(event_id,str) or not event_id.startswith('evt_') or
            event_type not in ('checkout.session.completed',
                               'checkout.session.async_payment_succeeded')):
        raise CheckoutVerificationError('A signed Stripe payment event is required.')
    proof=verify_level1a_paid_session(session,binding,expected_livemode)
    row=conn.execute('''SELECT * FROM level1a_checkout_sessions WHERE
        stripe_session_id=? AND tenant_id=? AND order_id=?''',
        (proof['session_id'],binding.tenant_id,binding.order_id)).fetchone()
    if not row or not _same(row,binding):
        raise CheckoutVerificationError('The paid Session is not bound to this order.')
    prior_event=conn.execute('SELECT * FROM level1a_payment_events WHERE stripe_event_id=?',
                             (event_id,)).fetchone()
    if prior_event:
        if prior_event['checkout_id']==row['id'] and prior_event['outcome'] in ('Paid','Held'):
            return dict(row)
        raise CheckoutVerificationError('The Stripe event was used for another order.')
    other=conn.execute('''SELECT id FROM level1a_checkout_sessions WHERE
        acceptance_id=? AND status='Paid' AND id<>?''',
        (binding.acceptance_id,row['id'])).fetchone()
    if other or row['status'] not in ('Pending','Paid'):
        raise CheckoutVerificationError('This agreement already has a conflicting payment.')
    if row['status']=='Paid' and row['payment_intent_id']!=proof['payment_intent']:
        raise CheckoutVerificationError('A paid Session cannot change payment identity.')
    prior_hold=conn.execute('''SELECT stripe_event_id FROM level1a_payment_holds WHERE
        payment_intent_id=? LIMIT 1''',(proof['payment_intent'],)).fetchone()
    status='Held' if prior_hold else 'Paid'
    paid_at=row['paid_at'] if row['status']=='Paid' else timestamp
    receipt=_receipt_digest(row,proof['payment_intent'],paid_at) if status=='Paid' else ''
    if row['status']=='Paid' and row['receipt_sha256']!=receipt:
        raise CheckoutVerificationError('The existing receipt changed.')
    conn.execute('''UPDATE level1a_checkout_sessions SET status=?,payment_intent_id=?,
        receipt_sha256=?,paid_at=? WHERE id=?''',
        (status,proof['payment_intent'],receipt,paid_at,row['id']))
    conn.execute('''INSERT INTO level1a_payment_events
        (stripe_event_id,checkout_id,event_type,outcome,processed_at)
        VALUES(?,?,?,?,?)''',(event_id,row['id'],event_type,status,timestamp))
    return dict(conn.execute('SELECT * FROM level1a_checkout_sessions WHERE id=?',
                             (row['id'],)).fetchone())


def hold_level1a_payment(conn,payment_intent_id,event_id,event_type,timestamp):
    if (not isinstance(payment_intent_id,str) or
            not payment_intent_id.startswith('pi_') or
            not isinstance(event_id,str) or not event_id.startswith('evt_') or
            event_type not in ('charge.refunded','charge.dispute.created',
                               'payment_intent.canceled','payment_intent.payment_failed')):
        raise CheckoutVerificationError('An identified adverse Stripe event is required.')
    conn.execute('''INSERT INTO level1a_payment_holds
        (stripe_event_id,payment_intent_id,event_type,recorded_at)
        VALUES(?,?,?,?) ON CONFLICT(stripe_event_id) DO NOTHING''',
        (event_id,payment_intent_id,event_type,timestamp))
    saved=conn.execute('SELECT * FROM level1a_payment_holds WHERE stripe_event_id=?',
                       (event_id,)).fetchone()
    if saved['payment_intent_id']!=payment_intent_id:
        raise CheckoutVerificationError('The adverse event identity changed.')
    row=conn.execute('''SELECT * FROM level1a_checkout_sessions WHERE
        payment_intent_id=? AND status IN ('Paid','Held')''',
        (payment_intent_id,)).fetchone()
    if not row:
        return None
    prior=conn.execute('SELECT * FROM level1a_payment_events WHERE stripe_event_id=?',
                       (event_id,)).fetchone()
    if prior:
        if prior['checkout_id']!=row['id'] or prior['outcome']!='Held':
            raise CheckoutVerificationError('The adverse event was used for another order.')
        return dict(row)
    conn.execute("UPDATE level1a_checkout_sessions SET status='Held' WHERE id=?",(row['id'],))
    conn.execute('''INSERT INTO level1a_payment_events
        (stripe_event_id,checkout_id,event_type,outcome,processed_at)
        VALUES(?,?,?,?,?)''',(event_id,row['id'],event_type,'Held',timestamp))
    return dict(conn.execute('SELECT * FROM level1a_checkout_sessions WHERE id=?',
                             (row['id'],)).fetchone())


def verified_level1a_receipt(conn,binding):
    rows=conn.execute('''SELECT * FROM level1a_checkout_sessions WHERE
        tenant_id=? AND buyer_user_id=? AND order_id=? AND acceptance_id=?
        AND status='Paid' ''',
        (binding.tenant_id,binding.buyer_user_id,binding.order_id,
         binding.acceptance_id)).fetchall()
    if not rows:
        return None
    if len(rows)!=1 or not _same(rows[0],binding):
        raise CheckoutVerificationError('The paid receipt identity is ambiguous.')
    row=rows[0]
    if (not row['payment_intent_id'] or not row['paid_at'] or
            row['receipt_sha256']!=_receipt_digest(row,row['payment_intent_id'],
                                                   row['paid_at'])):
        raise CheckoutVerificationError('The paid receipt failed integrity review.')
    return dict(row)


def record_level1a_receipt_document(conn,binding,checkout_id,content,stored_name,
                                    readback):
    """Record one content-addressed, exact-readback receipt for a paid order."""
    row=verified_level1a_receipt(conn,binding)
    if not row or row['id']!=checkout_id:
        raise CheckoutVerificationError('No verified payment may receive this document.')
    if (not isinstance(content,bytes) or not content.startswith(b'<!doctype html>') or
            len(content)>100_000 or readback!=content):
        raise CheckoutVerificationError('The saved receipt bytes failed integrity review.')
    digest=sha256(content).hexdigest()
    if stored_name!=f'level1a/{binding.tenant_id}/{binding.order_id}/receipts/{digest}.html':
        raise CheckoutVerificationError('The receipt storage key belongs to another order.')
    if row['receipt_document_sha256']:
        if (row['receipt_document_sha256']!=digest or
                row['receipt_stored_name']!=stored_name):
            raise CheckoutVerificationError('An immutable receipt already exists.')
        return row
    result=conn.execute('''UPDATE level1a_checkout_sessions SET
        receipt_document_sha256=?,receipt_stored_name=? WHERE id=? AND
        status='Paid' AND receipt_document_sha256='' ''',
        (digest,stored_name,checkout_id))
    if result.rowcount!=1:
        raise CheckoutVerificationError('The receipt changed before storage.')
    return dict(conn.execute('SELECT * FROM level1a_checkout_sessions WHERE id=?',
                             (checkout_id,)).fetchone())


def issued_level1a_receipt(conn,binding,readback):
    row=verified_level1a_receipt(conn,binding)
    if not row or not row['receipt_document_sha256'] or not row['receipt_stored_name']:
        return None
    if (not isinstance(readback,bytes) or
            sha256(readback).hexdigest()!=row['receipt_document_sha256']):
        raise CheckoutVerificationError('The stored receipt differs from the paid record.')
    return row
