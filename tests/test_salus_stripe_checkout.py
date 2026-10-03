import hashlib
import hmac
import json
import unittest

from salus_stripe_checkout import (
    CheckoutBinding, CheckoutVerificationError, checkout_form,
    create_checkout_session, verify_paid_session, verify_webhook_signature,
)


class StripeCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.binding = CheckoutBinding(7, 11, 13, 17, "a" * 64, "b" * 64, 150000)

    def test_session_request_binds_exact_quote_and_amount(self):
        seen = {}

        def transport(form, secret, key):
            seen.update(form=form, secret=secret, key=key)
            return {"id": "cs_test_one", "url": "https://checkout.stripe.com/pay/one"}

        result = create_checkout_session(self.binding, "sk_test_example", "https://salus.solutions/return",
                                         "https://salus.solutions/cancel", transport)
        self.assertEqual(result["id"], "cs_test_one")
        self.assertEqual(seen["form"]["line_items[0][price_data][unit_amount]"], "150000")
        self.assertEqual(seen["form"]["metadata[salus_quote_sha256]"], "a" * 64)
        self.assertTrue(seen["key"])

    def test_checkout_rejects_insecure_return_and_bad_binding(self):
        with self.assertRaises(CheckoutVerificationError):
            checkout_form(self.binding, "http://salus.solutions/return", "https://salus.solutions/cancel")
        with self.assertRaises(CheckoutVerificationError):
            CheckoutBinding(7, 11, 13, 17, "a" * 64, "b" * 64, 0)

    def test_webhook_requires_raw_body_signature_and_fresh_timestamp(self):
        payload = json.dumps({"id": "evt_1", "type": "checkout.session.completed"}).encode()
        digest = hmac.new(b"whsec_example", b"1000." + payload, hashlib.sha256).hexdigest()
        header = f"t=1000,v1={digest}"
        self.assertEqual(verify_webhook_signature(payload, header, "whsec_example", now_seconds=1000)["id"], "evt_1")
        for body, stamp_header, at in ((payload + b" ", header, 1000),
                                       (payload, header, 1301), (payload, "malformed", 1000)):
            with self.assertRaises(CheckoutVerificationError):
                verify_webhook_signature(body, stamp_header, "whsec_example", now_seconds=at)

    def test_paid_session_requires_exact_quote_amount_and_live_mode(self):
        session = {"id": "cs_test_one", "object": "checkout.session", "status": "complete",
                   "payment_status": "paid", "mode": "payment", "livemode": False,
                   "amount_total": 150000, "currency": "usd", "client_reference_id": "17",
                   "metadata": self.binding.metadata(), "payment_intent": "pi_test_one"}
        self.assertEqual(verify_paid_session(session, self.binding, False)["payment_intent"], "pi_test_one")
        for changed in ({"amount_total": 149999}, {"payment_status": "unpaid"},
                        {"metadata": {**self.binding.metadata(), "salus_quote_sha256": "c" * 64}},
                        {"livemode": True}, {"payment_intent": None}):
            with self.assertRaises(CheckoutVerificationError):
                verify_paid_session({**session, **changed}, self.binding, False)


if __name__ == "__main__":
    unittest.main()

