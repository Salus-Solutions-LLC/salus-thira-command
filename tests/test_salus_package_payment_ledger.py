import sqlite3
import unittest

from salus_stripe_checkout import CheckoutBinding, CheckoutVerificationError
from salus_package_payment_ledger import (
    ensure_payment_schema, paid_receipt, record_checkout_session, record_verified_payment,
    hold_payment_event,
)


class PackagePaymentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row
        ensure_payment_schema(self.conn)
        self.binding = CheckoutBinding(7, 11, 13, 17, 'a' * 64, 'b' * 64, 150000)
        self.session = {'id':'cs_test_12345678','object':'checkout.session','status':'complete',
                        'payment_status':'paid','mode':'payment','livemode':False,
                        'amount_total':150000,'currency':'usd','client_reference_id':'17',
                        'metadata':self.binding.metadata(),'payment_intent':'pi_test_one'}

    def tearDown(self):
        self.conn.close()

    def test_no_payment_no_intake_and_idempotent_paid_receipt(self):
        self.assertIsNone(paid_receipt(self.conn,self.binding))
        original = record_checkout_session(self.conn,self.binding,1,'cs_test_12345678',
            'https://checkout.stripe.com/pay/example','2026-10-03T01:00:00Z')
        self.assertEqual(original['status'],'Pending')
        self.assertIsNone(paid_receipt(self.conn,self.binding))
        repeated = record_checkout_session(self.conn,self.binding,1,'cs_test_12345678',
            'https://checkout.stripe.com/pay/example','2026-10-03T01:00:00Z')
        self.assertEqual(repeated['id'],original['id'])
        paid = record_verified_payment(self.conn,self.binding,self.session,'evt_1',
            '2026-10-03T01:01:00Z',False)
        self.assertEqual(paid['status'],'Paid')
        self.assertEqual(paid_receipt(self.conn,self.binding)['receipt_sha256'],paid['receipt_sha256'])
        self.assertEqual(record_verified_payment(self.conn,self.binding,self.session,'evt_1',
            '2026-10-03T01:02:00Z',False)['receipt_sha256'],paid['receipt_sha256'])
        self.assertEqual(record_verified_payment(self.conn,self.binding,self.session,'evt_2',
            '2026-10-03T01:03:00Z',False)['receipt_sha256'],paid['receipt_sha256'])

    def test_refund_or_dispute_holds_paid_package(self):
        record_checkout_session(self.conn,self.binding,1,'cs_test_12345678',
            'https://checkout.stripe.com/pay/example','2026-10-03T01:00:00Z')
        record_verified_payment(self.conn,self.binding,self.session,'evt_paid',
            '2026-10-03T01:01:00Z',False)
        held=hold_payment_event(self.conn,'pi_test_one','evt_refund',
            'charge.refunded','2026-10-03T01:02:00Z')
        self.assertEqual(held['status'],'Held')
        self.assertIsNone(paid_receipt(self.conn,self.binding))
        self.assertEqual(hold_payment_event(self.conn,'pi_test_one','evt_refund',
            'charge.refunded','2026-10-03T01:03:00Z')['status'],'Held')
        with self.assertRaises(CheckoutVerificationError):
            record_verified_payment(self.conn,self.binding,self.session,'evt_replay',
                '2026-10-03T01:04:00Z',False)
        self.assertIsNone(hold_payment_event(self.conn,'pi_other','evt_other',
            'charge.dispute.created','2026-10-03T01:05:00Z'))

    def test_wrong_amount_or_quote_cannot_authorize(self):
        record_checkout_session(self.conn,self.binding,1,'cs_test_12345678',
            'https://checkout.stripe.com/pay/example','2026-10-03T01:00:00Z')
        for changed in ({'amount_total':149999},
                        {'metadata':{**self.binding.metadata(),'salus_quote_sha256':'c'*64}}):
            with self.assertRaises(CheckoutVerificationError):
                record_verified_payment(self.conn,self.binding,{**self.session,**changed},
                    'evt_invalid','2026-10-03T01:01:00Z',False)
        self.assertIsNone(paid_receipt(self.conn,self.binding))

    def test_tampered_receipt_and_cross_tenant_event_rejected(self):
        record_checkout_session(self.conn,self.binding,1,'cs_test_12345678',
            'https://checkout.stripe.com/pay/example','2026-10-03T01:00:00Z')
        record_verified_payment(self.conn,self.binding,self.session,'evt_1','2026-10-03T01:01:00Z',False)
        self.conn.execute("UPDATE package_checkout_sessions SET receipt_sha256='wrong'")
        with self.assertRaises(CheckoutVerificationError):
            paid_receipt(self.conn,self.binding)
        with self.assertRaises(CheckoutVerificationError):
            record_verified_payment(self.conn,self.binding,self.session,'evt_2',
                '2026-10-03T01:02:00Z',False)
        another=CheckoutBinding(8, 22, 23, 27, 'c'*64, 'd'*64, 150000)
        self.assertIsNone(paid_receipt(self.conn,another))


if __name__ == '__main__':
    unittest.main()

