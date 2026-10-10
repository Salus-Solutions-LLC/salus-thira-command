"""Stripe Checkout facts for one accepted standard Level 1A order.

The recorded SAL-D106 Level 1A U.S.-buyer zero-tax rule supports this fixed
$1,500 Checkout. Other countries and any changed tax result remain closed.
"""

from dataclasses import dataclass
from hashlib import sha256

from salus_stripe_checkout import (CheckoutVerificationError, _require_https,
                                   _stripe_post)


@dataclass(frozen=True)
class Level1ACheckoutBinding:
    tenant_id: int
    buyer_user_id: int
    order_id: int
    quote_id: int
    acceptance_id: int
    scope_sha256: str
    quote_sha256: str
    agreement_sha256: str
    base_price_cents: int
    tax_cents: int
    amount_cents: int
    currency: str = 'usd'

    def __post_init__(self):
        if any(type(value) is not int or value <= 0 for value in
               (self.tenant_id,self.buyer_user_id,self.order_id,self.quote_id,
                self.acceptance_id)):
            raise CheckoutVerificationError('Checkout requires saved buyer and agreement identifiers.')
        if any(len(value)!=64 or any(ch not in '0123456789abcdef' for ch in value)
               for value in (self.scope_sha256,self.quote_sha256,
                             self.agreement_sha256)):
            raise CheckoutVerificationError('Checkout requires exact scope and agreement hashes.')
        if (self.base_price_cents!=150_000 or self.tax_cents!=0 or
                self.amount_cents!=150_000 or self.currency!='usd'):
            raise CheckoutVerificationError('Only the approved $1,500 Level 1A total with the recorded zero-tax quote is enabled.')

    def metadata(self):
        return {'salus_product':'level1a_access',
                'salus_tenant_id':str(self.tenant_id),
                'salus_buyer_user_id':str(self.buyer_user_id),
                'salus_order_id':str(self.order_id),
                'salus_quote_id':str(self.quote_id),
                'salus_acceptance_id':str(self.acceptance_id),
                'salus_scope_sha256':self.scope_sha256,
                'salus_quote_sha256':self.quote_sha256,
                'salus_agreement_sha256':self.agreement_sha256}


def level1a_checkout_form(binding, success_url, cancel_url):
    _require_https(success_url)
    _require_https(cancel_url)
    form={'mode':'payment','payment_method_types[0]':'card',
          'client_reference_id':str(binding.acceptance_id),
          'success_url':success_url,'cancel_url':cancel_url,
          'line_items[0][price_data][currency]':binding.currency,
          'line_items[0][price_data][unit_amount]':str(binding.base_price_cents),
          'line_items[0][price_data][product_data][name]':'Salus Level 1A Access assessment',
          'line_items[0][quantity]':'1',
          'automatic_tax[enabled]':'false'}
    form.update({f'metadata[{key}]':value for key,value in binding.metadata().items()})
    return form


def create_level1a_checkout_session(binding, secret_key, success_url, cancel_url,
                                    *, attempt_no=1, transport=None):
    if type(attempt_no) is not int or not 1<=attempt_no<=20:
        raise CheckoutVerificationError('The checkout retry count requires review.')
    if not isinstance(secret_key,str) or not secret_key.startswith(
            ('sk_test_','sk_live_','rk_test_','rk_live_')):
        raise CheckoutVerificationError('A Stripe secret key is required.')
    form=level1a_checkout_form(binding,success_url,cancel_url)
    retry_key=sha256(f'level1a:{binding.acceptance_id}:{binding.quote_sha256}:'
                     f'{attempt_no}'.encode('ascii')).hexdigest()
    session=(transport or _stripe_post)(form,secret_key,retry_key)
    if (not isinstance(session,dict) or not isinstance(session.get('id'),str) or
            not session['id'].startswith('cs_') or
            not isinstance(session.get('url'),str) or
            not session['url'].startswith('https://checkout.stripe.com/')):
        raise CheckoutVerificationError('Stripe did not return a usable Checkout Session.')
    return {'id':session['id'],'url':session['url']}


def verify_level1a_paid_session(session, binding, expected_livemode):
    if (not isinstance(session,dict) or session.get('object')!='checkout.session' or
            not session.get('id') or session.get('status')!='complete' or
            session.get('payment_status')!='paid' or session.get('mode')!='payment' or
            session.get('livemode') is not expected_livemode):
        raise CheckoutVerificationError('The retrieved Checkout Session is not paid in this mode.')
    if (session.get('amount_subtotal')!=binding.base_price_cents or
            session.get('amount_total')!=binding.amount_cents or
            session.get('currency')!=binding.currency or
            (session.get('total_details') or {}).get('amount_tax')!=binding.tax_cents):
        raise CheckoutVerificationError('The paid subtotal, tax or total differs from the quote.')
    if (session.get('client_reference_id')!=str(binding.acceptance_id) or
            session.get('metadata')!=binding.metadata() or
            not session.get('payment_intent')):
        raise CheckoutVerificationError('The paid Session differs from the accepted agreement.')
    return {'session_id':session['id'],'payment_intent':session['payment_intent']}
