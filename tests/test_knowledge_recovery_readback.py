import copy
import contextlib
import io
import json
import os
import sqlite3
import tempfile
import unittest
from tools import live_knowledge_recovery_readback as readback

STAMP = "2026-11-15T18:00:00+00:00"
SCHEMA = """
CREATE TABLE m365_knowledge_consideration_receipts(receipt_id TEXT,query_sha256 TEXT,boundary_count INTEGER,
 considered_count INTEGER,matched_count INTEGER,content_available_count INTEGER,metadata_only_count INTEGER,
 governed_hold_count INTEGER,actor TEXT,created_at TEXT);
CREATE TABLE m365_knowledge_recovery_plans(operation_key TEXT PRIMARY KEY,state TEXT,manifest_sha256 TEXT,payload_json TEXT,created_at TEXT);
CREATE TABLE m365_knowledge_recovery_batches(operation_key TEXT,batch_key TEXT,record_count INTEGER,payload_sha256 TEXT,payload_json TEXT);
CREATE TABLE m365_knowledge_recovery_plan_events(operation_key TEXT,event_type TEXT,detail_json TEXT,created_at TEXT);
"""
ALL_TABLES = (*readback.TABLES, "m365_knowledge_consideration_receipts")


def fixture():
    batches, n = [], 0
    for category, count in readback.CATEGORIES.items():
        records = []
        for _ in range(count):
            n += 1
            source = "PRIVATE-SOURCE-" + str(n)
            statuses = {"governed_review": ["Review Required"], "retry_paused": ["Retry Paused"],
                "automatic_retry": ["Automatic Retry Required"], "governed_hold": [],
                "other_or_conflicting": ["Review Required", "Retry Paused"]}[category]
            records.append({"source_item_id": source, "category": category, "failure_codes": ["PDF_ENCRYPTED"],
                "processing_authorized": False, "human_qualification": "Unvetted Candidate",
                "holds": [{"status": "Governed Hold"}] if category == "governed_hold" else [],
                "candidate_versions": [{"source_item_id": source, "extraction_status": s,
                    "legacy_complete": 0, "archive_bytes_verified_by_this_task": False} for s in statuses]})
        for start in range(0, len(records), 50):
            group = records[start:start + 50]
            batches.append({"batch_key": "batch-" + str(len(batches)), "records": group, "record_count": len(group),
                "state": readback.STATE, "processing_authorized": False, "category": category, "failure_codes": ["PDF_ENCRYPTED"]})
    exceptions = [{"source_item_id": "PRIVATE-EXCEPTION-" + str(n), "processing_authorized": False,
        "human_qualification": "Unvetted Candidate", "candidate_versions": [{"source_item_id": "PRIVATE-EXCEPTION-" + str(n),
            "extraction_status": "Complete", "has_text": 0, "legacy_complete": 1, "availability_condition": "EXACT_COMPLETE_EMPTY_TEXT"}]} for n in range(5)]
    summary = {"categories": readback.CATEGORIES, "unresolved_files": 8404, "prepared_sources": 8404,
        "represented_files": 23632, "legacy_content_available": 15228, "exact_complete_nonempty_text": 15223,
        "strict_complete_text": 15223, "availability_exceptions": 5, "processing_authorized": False,
        "batch_count": len(batches), "availability_candidate_conditions": {"EXACT_COMPLETE_EMPTY_TEXT": 5}}
    manifest = {"operation_key": readback.OPERATION, "state": readback.STATE, "created_at": STAMP,
        "inventory_sha256": "a" * 64, "evidence_sha256": "b" * 64, "summary": summary,
        "availability_exceptions": exceptions,
        "batch_hashes": [{"batch_key": b["batch_key"], "sha256": readback.digest(b)} for b in batches]}
    return manifest, batches


class ReadbackTests(unittest.TestCase):
    def connect(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        return c

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.folder.name, "readback.db")
        self.conn = self.connect()
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        self.folder.cleanup()

    def seed(self, receipt_count=4, plan=True):
        for n, (label, query) in enumerate(readback.QUERIES[:receipt_count]):
            self.conn.execute("INSERT INTO m365_knowledge_consideration_receipts VALUES(?,?,?,?,?,?,?,?,?,?)",
                (f"00000000-0000-0000-0000-{n:012d}", readback.hashlib.sha256(query.encode()).hexdigest(),
                 23622, 23632, 100, 15228, 8404, 93, readback.ACTOR + label, STAMP))
        if plan:
            manifest, batches = fixture()
            checksum = readback.digest(manifest)
            self.conn.execute("INSERT INTO m365_knowledge_recovery_plans VALUES(?,?,?,?,?)",
                (readback.OPERATION, readback.STATE, checksum, readback.canonical(manifest), STAMP))
            for b in batches:
                self.conn.execute("INSERT INTO m365_knowledge_recovery_batches VALUES(?,?,?,?,?)",
                    (readback.OPERATION, b["batch_key"], b["record_count"], readback.digest(b), readback.canonical(b)))
            self.conn.execute("INSERT INTO m365_knowledge_recovery_plan_events VALUES(?,?,?,?)",
                (readback.OPERATION, "AvailabilityReconciledAndRecoveryBatchesPrepared",
                 readback.canonical({"manifest_sha256": checksum, "summary": manifest["summary"], "processing_authorized": False}), STAMP))
        self.conn.commit()

    def test_full_8404_partition_and_five_separate_exceptions_read_back_twice_without_writes(self):
        self.seed()
        result = readback.reconcile(self.conn)
        self.assertTrue(result["complete_preparation_verified"])
        self.assertEqual(result["durable_state"], "COMPLETE_PREPARED")
        self.assertEqual(result["receipt_count"], 4)
        fresh = self.connect()
        try: self.assertEqual(readback.reconcile(fresh), result)
        finally: fresh.close()
        with self.assertRaises(Exception): self.conn.execute("DELETE FROM m365_knowledge_recovery_batches")

    def test_empty_and_partial_receipts_are_reported_without_inventing_a_plan(self):
        for count in (0, 2, 4):
            self.conn.close()
            self.conn = self.connect()
            self.conn.execute("DELETE FROM m365_knowledge_consideration_receipts")
            self.conn.commit()
            self.seed(receipt_count=count, plan=False)
            result = readback.reconcile(self.conn)
            self.assertFalse(result["complete_preparation_verified"])
            self.assertEqual(result["receipt_count"], count)
            self.assertEqual(result["plan_count"], 0)

    def test_absent_planning_tables_are_a_valid_empty_observation(self):
        for t in readback.TABLES: self.conn.execute("DROP TABLE " + t)
        self.conn.commit()
        self.assertEqual(readback.reconcile(self.conn)["durable_state"], "EMPTY")

    def test_manifest_hash_batch_count_and_event_corruption_each_fail_closed(self):
        self.seed()
        for table, field, value in ((readback.TABLES[0], "manifest_sha256", "bad"),
                                    (readback.TABLES[1], "record_count", 999),
                                    (readback.TABLES[2], "detail_json", "bad")):
            self.conn.close()
            self.conn = self.connect()
            baseline = [dict(r) for r in self.conn.execute("SELECT * FROM " + table).fetchall()]
            self.conn.execute("UPDATE " + table + " SET " + field + "=?", (value,))
            self.conn.commit()
            with self.assertRaises(ValueError): readback.reconcile(self.conn)
            self.conn.close()
            self.conn = self.connect()
            for r in baseline:
                sql = "UPDATE " + table + " SET " + field + "=? WHERE operation_key=?"
                params = (r[field], readback.OPERATION)
                if "batch_key" in r: sql += " AND batch_key=?"; params += (r["batch_key"],)
                self.conn.execute(sql, params)
            self.conn.commit()

    def test_missing_receipts_or_orphan_rows_cannot_be_accepted_as_preparation(self):
        self.seed(receipt_count=3)
        with self.assertRaises(ValueError): readback.reconcile(self.conn)
        self.conn.close()
        self.conn = self.connect()
        self.conn.execute("DELETE FROM m365_knowledge_recovery_plans")
        self.conn.commit()
        with self.assertRaises(ValueError): readback.reconcile(self.conn)

    def test_duplicate_source_membership_is_detected_even_with_rehashed_payload(self):
        self.seed()
        manifest = json.loads(self.conn.execute("SELECT payload_json FROM m365_knowledge_recovery_plans").fetchone()[0])
        b = dict(self.conn.execute("SELECT * FROM m365_knowledge_recovery_batches WHERE batch_key='batch-0'").fetchone())
        payload = json.loads(b["payload_json"])
        payload["records"][1]["source_item_id"] = payload["records"][0]["source_item_id"]
        checksum = readback.digest(payload)
        self.conn.execute("UPDATE m365_knowledge_recovery_batches SET payload_json=?,payload_sha256=? WHERE batch_key='batch-0'", (readback.canonical(payload), checksum))
        for r in manifest["batch_hashes"]:
            if r["batch_key"] == "batch-0": r["sha256"] = checksum
        self.conn.execute("UPDATE m365_knowledge_recovery_plans SET payload_json=?,manifest_sha256=?", (readback.canonical(manifest), readback.digest(manifest)))
        self.conn.commit()
        with self.assertRaises(ValueError): readback.reconcile(self.conn)

    def test_private_payload_never_appears_in_telemetry(self):
        self.seed()
        result = readback.reconcile(self.conn)
        with contextlib.redirect_stdout(io.StringIO()) as out: readback.emit(result)
        self.assertNotIn("PRIVATE", out.getvalue())
        self.assertNotIn("source_item_id", out.getvalue())
        self.assertIn("DATABASE_WRITES=0", out.getvalue())


@unittest.skipUnless(os.getenv("TEST_RECOVERY_READBACK_POSTGRES") == "1", "dedicated PostgreSQL CI only")
class PostgreSQLReadbackTests(ReadbackTests):
    def connect(self):
        from database import connect_database
        return connect_database()

    def setUp(self):
        assert os.getenv("SALUS_DATABASE_URL", "").startswith("postgresql://postgres:postgres@localhost:5432/recovery_readback") # repo-hygiene: allow - localhost-only ephemeral PostgreSQL CI fixture
        c = self.connect()
        for t in ALL_TABLES: c.execute("DROP TABLE IF EXISTS " + t)
        c.commit()
        c.close()
        super().setUp()

    def tearDown(self):
        self.conn.close()
        c = self.connect()
        for t in ALL_TABLES: c.execute("DROP TABLE IF EXISTS " + t)
        c.commit()
        c.close()
        self.folder.cleanup()


if __name__ == "__main__": unittest.main()
