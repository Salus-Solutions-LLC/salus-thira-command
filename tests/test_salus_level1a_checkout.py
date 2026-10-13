"""The fixed Level 1A Checkout Session must match the accepted scope."""

import pytest

from salus_level1a_checkout import (
    Level1ACheckoutBinding, create_level1a_checkout_session,
    validate_level1a_checkout_key, verify_level1a_paid_session,
)
from salus_stripe_checkout import CheckoutVerificationError


def _binding():
    return Level1ACheckoutBinding(1,2,3,4,5,'a'*64,'b'*64,'c'*64,
                                  150_000,0,150_000)


def _paid(binding):
    return {'id':'cs_test_example12345678','object':'checkout.session',
            'status':'complete','payment_status':'paid','mode':'payment',
            'livemode':False,'amount_subtotal':150_000,'amount_total':150_000,
            'currency':'usd','total_details':{'amount_tax':0},
            'client_reference_id':'5','metadata':binding.metadata(),
            'payment_intent':'pi_fictional'}


def test_checkout_form_and_retrieved_payment_bind_exact_approved_terms():
    binding=_binding()
    captured={}
    def fake_post(form,key,retry):
        captured.update(form)
        assert key=='rk_test_fictional' and len(retry)==64
        return {'id':'cs_test_example12345678',
                'url':'https://checkout.stripe.com/c/pay/fictional'}
    session=create_level1a_checkout_session(
        binding,'rk_test_fictional','https://salcapa.salus.solutions/success',
        'https://salcapa.salus.solutions/cancel',transport=fake_post)
    assert session['id']=='cs_test_example12345678'
    assert captured['line_items[0][price_data][unit_amount]']=='150000'
    assert captured['automatic_tax[enabled]']=='false'
    assert captured['metadata[salus_agreement_sha256]']=='c'*64
    assert verify_level1a_paid_session(_paid(binding),binding,False)['payment_intent']=='pi_fictional'


@pytest.mark.parametrize('change',[
    {'amount_total':149_999},{'amount_subtotal':149_999},
    {'total_details':{'amount_tax':1}},{'status':'open'},
    {'payment_status':'unpaid'},{'livemode':True},
    {'metadata':{}},{'payment_intent':''},
])
def test_checkout_rejects_wrong_retrieved_payment(change):
    binding=_binding()
    with pytest.raises(CheckoutVerificationError):
        verify_level1a_paid_session(_paid(binding)|change,binding,False)


def test_checkout_rejects_other_tax_and_price():
    with pytest.raises(CheckoutVerificationError):
        Level1ACheckoutBinding(1,2,3,4,5,'a'*64,'b'*64,'c'*64,
                               150_000,1,150_001)


def test_protected_pilot_rejects_live_key_before_reusing_or_creating_checkout():
    binding=_binding()
    calls=[]
    def fake_post(*args):
        calls.append(args)
        raise AssertionError('Live Stripe must never receive a pilot request.')
    with pytest.raises(CheckoutVerificationError,match='test keys only'):
        validate_level1a_checkout_key('sk_live_fictional',test_only=True)
    with pytest.raises(CheckoutVerificationError,match='test keys only'):
        create_level1a_checkout_session(
            binding,'sk_live_fictional',
            'https://salcapa.salus.solutions/success',
            'https://salcapa.salus.solutions/cancel',
            transport=fake_post,test_only=True)
    assert calls==[]
    validate_level1a_checkout_key('rk_test_fictional',test_only=True)
