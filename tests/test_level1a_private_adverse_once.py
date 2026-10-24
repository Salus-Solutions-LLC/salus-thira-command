"""A protected EICAR run cannot select an unrelated or already-used buyer item."""

import sqlite3
from types import SimpleNamespace
import unittest

from tools import level1a_private_adverse_once as adverse


def _fixture():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE users (id INTEGER,tenant_id INTEGER,email TEXT,identity_provider TEXT);
        CREATE TABLE level1a_orders (id INTEGER,tenant_id INTEGER,buyer_user_id INTEGER,
            buyer_legal_name TEXT,unit_name TEXT);
        CREATE TABLE level1a_assessment_links (order_id INTEGER,tenant_id INTEGER,
            buyer_user_id INTEGER,scope_sha256 TEXT,assessment_id INTEGER);
        CREATE TABLE level1a_intake_items (id INTEGER,tenant_id INTEGER,order_id INTEGER,
            title TEXT,assessment_id INTEGER,status TEXT);
        CREATE TABLE level1a_disclosure_authority (order_id INTEGER,tenant_id INTEGER,
            buyer_user_id INTEGER,scope_sha256 TEXT,statement_version TEXT);
        CREATE TABLE level1a_pending_scans (tenant_id INTEGER,intake_request_id INTEGER,
            order_id INTEGER,content_sha256 TEXT);
        CREATE TABLE level1a_intake_uploads (tenant_id INTEGER,intake_request_id INTEGER);
        INSERT INTO users VALUES (7,3,'MDuncan@Salus.Solutions','entra_customer');
        INSERT INTO level1a_orders VALUES (10,3,7,'Fictional Cedar Works LLC','Fictional Cedar Site');
        INSERT INTO level1a_assessment_links VALUES (10,3,7,'exact-scope',5);
        INSERT INTO level1a_intake_items VALUES
            (12,3,10,'Leadership priorities and constraints',5,'Requested');
        INSERT INTO level1a_disclosure_authority VALUES
            (10,3,7,'exact-scope','v1');
    """)
    app = SimpleNamespace(
        CUSTOMER_PROVIDER="entra_customer",
        DISCLOSURE_STATEMENT_VERSION="v1",
        LEVEL1A_INTAKE_ENABLED=False,
        _paid_level1a_intake=lambda *args: (SimpleNamespace(scope_sha256="exact-scope"), {}),
    )
    return conn, app


class PrivateAdverseTargetTests(unittest.TestCase):
    def test_exact_existing_paid_item_is_selected_without_changing_process_gate(self):
        conn, app = _fixture()
        try:
            target = adverse._target(conn, app, "sample-sha")
            self.assertEqual(target, {"tenant_id": 3, "user_id": 7,
                                      "assessment_id": 5, "item_id": 12})
            self.assertIs(app.LEVEL1A_INTAKE_ENABLED, False)
        finally:
            conn.close()

    def test_wrong_identity_or_used_item_fails_closed(self):
        for change in (
            "UPDATE users SET email='other@example.com' WHERE id=7",
            "UPDATE level1a_intake_items SET status='Not held' WHERE id=12",
            "DELETE FROM level1a_disclosure_authority",
            "INSERT INTO level1a_pending_scans VALUES (3,12,10,'sample-sha')",
            "INSERT INTO level1a_intake_uploads VALUES (3,12)",
        ):
            with self.subTest(change=change):
                conn, app = _fixture()
                try:
                    conn.execute(change)
                    with self.assertRaises(RuntimeError):
                        adverse._target(conn, app, "sample-sha")
                    self.assertIs(app.LEVEL1A_INTAKE_ENABLED, False)
                finally:
                    conn.close()
