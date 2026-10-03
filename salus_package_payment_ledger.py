"""Tenant-bound, auditable payment records for the gated package workflow.

The caller owns the database transaction. Never mark a payment Paid from a
browser redirect or webhook JSON alone: verify the raw-body signature, retrieve
the Session directly from Stripe, and call verify_paid_session first.
"""

import hashlib
import json

from salus_stripe_checkout import CheckoutVerificationError, verify_paid_session


PAYMENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS package_checkout_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    quote_id INTEGER NOT NULL,
    acceptance_id INTEGER NOT NULL,
    attempt_no INTEGER NOT NULL,
    stripe_session_id TEXT NOT NULL UNIQUE,
    checkout_url TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    currency TEXT NOT NULL,
    quote_sha256 TEXT NOT NULL,
    agreement_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending',
    payment_intent_id TEXT NOT NULL DEFAULT '',
    receipt_sha256 TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    paid_at TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (quote_id) REFERENCES package_quote_versions(id) ON DELETE RESTRICT,
    FOREIGN KEY (acceptance_id) REFERENCES package_acceptances(id) ON DELETE RESTRICT,
    UNIQUE (acceptance_id,attempt_no)
);
CREATE INDEX IF NOT EXISTS idx_package_checkout_scope
    ON package_checkout_sessions(tenant_id,assessment_id,quote_id,acceptance_id);
CREATE TABLE IF NOT EXISTS package_payment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id INTEGER NOT NULL,
    assessment_id INTEGER NOT NULL,
    checkout_id INTEGER NOT NULL,
    stripe_event_id TEXT NOT NULL UNIQUE,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    processed_at TEXT NOT NULL,
    FOREIGN KEY (tenant_id) REFERENCES tenants(id) ON DELETE CASCADE,
    FOREIGN KEY (assessment_id) REFERENCES assessments(id) ON DELETE CASCADE,
    FOREIGN KEY (checkout_id) REFERENCES package_checkout_sessions(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_package_payment_events_scope
    ON package_payment_events(tenant_id,assessment_id,checkout_id);
"""


def ensure_payment_schema(conn):
    conn.executescript(PAYMENT_SCHEMA)


def _exact(row, binding):
    return (row['tenant_id'] == binding.tenant_id and
            row['assessment_id'] == binding.assessment_id and
            row['quote_id'] == binding.quote_id and
            row['acceptance_id'] == binding.acceptance_id and
            row['amount_cents'] == binding.amount_cents and
            row['currency'] == binding.currency and
            row['quote_sha256'] == binding.quote_sha256 and
            row['agreement_sha256'] == binding.agreement_sha256)


def record_checkout_session(conn, binding, attempt_no, session_id, checkout_url, created_at):
    if attempt_no <= 0 or not session_id.startswith('cs_') or not checkout_url.startswith('https://checkout.stripe.com/'):
        raise CheckoutVerificationError('The Checkout Session response is not valid.')
    prior = conn.execute('''SELECT * FROM package_checkout_sessions
        WHERE acceptance_id=? AND attempt_no=?''', (binding.acceptance_id,attempt_no)).fetchone()
    if prior:
        if not _exact(prior,binding) or prior['stripe_session_id'] != session_id:
            raise CheckoutVerificationError('This checkout attempt is already bound to different terms.')
        return dict(prior)
    cur = conn.execute('''INSERT INTO package_checkout_sessions
        (tenant_id,assessment_id,quote_id,acceptance_id,attempt_no,stripe_session_id,checkout_url,
         amount_cents,currency,quote_sha256,agreement_sha256,status,created_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (binding.tenant_id,binding.assessment_id,binding.quote_id,binding.acceptance_id,
         attempt_no,session_id,checkout_url,binding.amount_cents,binding.currency,
         binding.quote_sha256,binding.agreement_sha256,'Pending',created_at))
    return dict(conn.execute('SELECT * FROM package_checkout_sessions WHERE id=?',(cur.lastrowid,)).fetchone())


def _receipt_payload(row, payment_intent_id, paid_at):
    return {key: row[key] for key in ('tenant_id','assessment_id','quote_id','acceptance_id',
                                     'stripe_session_id','amount_cents','currency',
                                     'quote_sha256','agreement_sha256')} | {
        'payment_intent_id':payment_intent_id, 'paid_at':paid_at,
    }


def record_verified_payment(conn, binding, session, stripe_event_id, paid_at, expected_livemode):
    if not stripe_event_id.startswith('evt_'):
        raise CheckoutVerificationError('A signed Stripe event identity is required.')
    proof = verify_paid_session(session,binding,expected_livemode)
    row = conn.execute('''SELECT * FROM package_checkout_sessions WHERE stripe_session_id=?
        AND tenant_id=? AND assessment_id=?''',
        (proof['session_id'],binding.tenant_id,binding.assessment_id)).fetchone()
    if not row or not _exact(row,binding):
        raise CheckoutVerificationError('The paid Session is not bound to the accepted package.')
    existing_event = conn.execute('SELECT * FROM package_payment_events WHERE stripe_event_id=?',
                                  (stripe_event_id,)).fetchone()
    if existing_event:
        if existing_event['checkout_id'] == row['id'] and existing_event['outcome'] == 'Paid':
            return dict(row)
        raise CheckoutVerificationError('This Stripe event was used for a different decision.')
    other = conn.execute('''SELECT id FROM package_checkout_sessions
        WHERE acceptance_id=? AND status='Paid' AND id<>?''',(binding.acceptance_id,row['id'])).fetchone()
    if other:
        raise CheckoutVerificationError('A different Checkout Session already paid this acceptance.')
    if row['status'] not in ('Pending','Paid'):
        raise CheckoutVerificationError('This Checkout Session cannot authorize the package.')
    if row['status']=='Paid' and row['payment_intent_id'] != proof['payment_intent']:
        raise CheckoutVerificationError('A paid Session cannot change payment identity.')
    effective_paid_at = row['paid_at'] if row['status']=='Paid' else paid_at
    receipt = hashlib.sha256(json.dumps(
        _receipt_payload(row,proof['payment_intent'],effective_paid_at),
        sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    if row['status']=='Paid' and row['receipt_sha256'] != receipt:
        raise CheckoutVerificationError('The existing payment receipt failed integrity review.')
    conn.execute('''UPDATE package_checkout_sessions SET status='Paid',payment_intent_id=?,
        receipt_sha256=?,paid_at=? WHERE id=?''',
        (proof['payment_intent'],receipt,effective_paid_at,row['id']))
    conn.execute('''INSERT INTO package_payment_events
        (tenant_id,assessment_id,checkout_id,stripe_event_id,event_type,outcome,processed_at)
        VALUES(?,?,?,?,?,?,?)''',
        (binding.tenant_id,binding.assessment_id,row['id'],stripe_event_id,
         'checkout.session.completed','Paid',paid_at))
    return dict(conn.execute('SELECT * FROM package_checkout_sessions WHERE id=?',(row['id'],)).fetchone())


def paid_receipt(conn, binding):
    rows = conn.execute('''SELECT * FROM package_checkout_sessions WHERE tenant_id=?
        AND assessment_id=? AND acceptance_id=? AND status='Paid' ''',
        (binding.tenant_id,binding.assessment_id,binding.acceptance_id)).fetchall()
    if len(rows) != 1 or not _exact(rows[0],binding):
        return None
    row = rows[0]
    expected = hashlib.sha256(json.dumps(
        _receipt_payload(row,row['payment_intent_id'],row['paid_at']),
        sort_keys=True,separators=(',',':')).encode('utf-8')).hexdigest()
    if not row['payment_intent_id'] or not row['paid_at'] or row['receipt_sha256'] != expected:
        raise CheckoutVerificationError('The paid receipt failed integrity review.')
    return dict(row)

