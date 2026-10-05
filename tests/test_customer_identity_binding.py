"""Provider-subject identity must never join buyers by email or employer name."""

import sqlite3

import unittest

from salus_customer_identity import bind_verified_buyer, identity_hash


def new_connection():
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys=ON')
    connection.executescript('''
        CREATE TABLE tenants (id INTEGER PRIMARY KEY, name TEXT NOT NULL,
            slug TEXT NOT NULL UNIQUE, status TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE users (id INTEGER PRIMARY KEY, tenant_id INTEGER NOT NULL,
            username TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL,
            sensitivity_clearance TEXT NOT NULL, status TEXT NOT NULL,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            email TEXT NOT NULL, external_subject TEXT NOT NULL,
            identity_provider TEXT NOT NULL,
            FOREIGN KEY(tenant_id) REFERENCES tenants(id));
        CREATE TABLE customer_identity_bindings (provider TEXT NOT NULL,
            subject_sha256 TEXT NOT NULL, tenant_id INTEGER NOT NULL UNIQUE,
            user_id INTEGER NOT NULL UNIQUE, created_at TEXT NOT NULL,
            PRIMARY KEY(provider,subject_sha256),
            FOREIGN KEY(tenant_id) REFERENCES tenants(id),
            FOREIGN KEY(user_id) REFERENCES users(id));
    ''')
    return connection


def bind(conn, subject, email='buyer@example.test', issuer='https://issuer.example.test'):
    return bind_verified_buyer(conn, issuer=issuer, subject=subject,
                               email=email, display_name='Fictional Buyer',
                               timestamp='2026-10-05T17:00:00Z')


class BuyerBindingTests(unittest.TestCase):
    def setUp(self):
        self.conn = new_connection()

    def tearDown(self):
        self.conn.close()

    def test_repeat_signin_and_changed_email_keep_the_same_isolated_identity(self):
        original = bind(self.conn, 'buyer-a')
        self.assertTrue(original[2])
        self.assertEqual(bind(self.conn, 'buyer-a', 'renamed@example.test'),
                         (original[0], original[1], False))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tenants').fetchone()[0], 1)
        self.assertEqual(self.conn.execute('SELECT count(*) FROM users').fetchone()[0], 1)

    def test_same_email_different_subject_or_issuer_never_joins_a_member(self):
        first = bind(self.conn, 'buyer-a')
        second = bind(self.conn, 'buyer-b')
        third = bind(self.conn, 'buyer-a', issuer='https://other.example.test')
        self.assertEqual(len({first[0], second[0], third[0]}), 3)
        self.assertEqual(len({first[1], second[1], third[1]}), 3)

    def test_inactive_or_tampered_binding_fails_closed(self):
        tenant_id, user_id, _ = bind(self.conn, 'buyer-a')
        self.conn.execute("UPDATE users SET identity_provider='entra' WHERE id=?", (user_id,))
        with self.assertRaisesRegex(ValueError, 'inconsistent'):
            bind(self.conn, 'buyer-a')
        self.conn.execute("UPDATE users SET identity_provider='entra_customer' WHERE id=?", (user_id,))
        self.conn.execute("UPDATE tenants SET status='Suspended' WHERE id=?", (tenant_id,))
        with self.assertRaisesRegex(ValueError, 'inactive'):
            bind(self.conn, 'buyer-a')

    def test_unverified_identity_inputs_do_not_create_a_member(self):
        for issuer, subject, email in (('', 'a', 'buyer@example.test'),
                                       ('https://issuer.example.test', '', 'buyer@example.test'),
                                       ('https://issuer.example.test', 'a', '')):
            with self.assertRaises(ValueError):
                bind_verified_buyer(self.conn, issuer=issuer, subject=subject,
                    email=email, display_name='Fictional Buyer',
                    timestamp='2026-10-05T17:00:00Z')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM tenants').fetchone()[0], 0)

    def test_subject_digest_does_not_expose_raw_subject(self):
        bind(self.conn, 'private-provider-subject')
        digest = self.conn.execute('SELECT subject_sha256 FROM customer_identity_bindings').fetchone()[0]
        self.assertEqual(digest, identity_hash('https://issuer.example.test', 'private-provider-subject'))
        self.assertNotIn('private-provider-subject', digest)


if __name__ == '__main__':
    unittest.main()
