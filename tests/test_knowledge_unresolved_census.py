"""Verify recovery census partitions, ambiguous availability and read-only behavior."""
import json
import sqlite3
import unittest
from tools.live_knowledge_unresolved_census import unresolved_snapshot

class CensusTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY, source_item_id TEXT, source_sha256 TEXT,
          source_archive_item_id TEXT, classification_json TEXT);
        CREATE TABLE m365_knowledge_holds(source_item_id TEXT,status TEXT);
        CREATE TABLE m365_bulk_items(item_id TEXT,kind TEXT,status TEXT);
        """)
    def tearDown(self):
        self.conn.close()
    def add(self, source, status, code="", text="", extra=None, compact=False):
        value = {"extraction":{"status":status,"failure_code":code,"text":text}}
        if extra:
            value.update(extra)
        encoded = json.dumps(value, separators=(",",":") if compact else None)
        self.conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?)",
                          (None,source,"sha","archive",encoded))
    def test_partition_preserves_holds_pauses_and_conflicts(self):
        self.add("review","Review Required","PDF_ENCRYPTED")
        self.add("paused","Retry Paused","IMAGE_RESOURCE_LIMIT")
        self.add("retry","Automatic Retry Required","OCR_RESOURCE_LIMIT")
        self.add("unknown","unexpected","private code / secret")
        self.add("conflict","Review Required","PDF_ACTIVE_CONTENT")
        self.add("conflict","Retry Paused","IMAGE_RESOURCE_LIMIT")
        self.conn.execute("INSERT INTO m365_knowledge_holds VALUES('hold','Governed Hold')")
        self.conn.execute("INSERT INTO m365_bulk_items VALUES('bulk','file','Pending')")
        self.conn.commit()
        self.conn.set_authorizer(lambda action, *args: sqlite3.SQLITE_DENY
            if action in (sqlite3.SQLITE_INSERT,sqlite3.SQLITE_UPDATE,sqlite3.SQLITE_DELETE,
                          sqlite3.SQLITE_CREATE_TABLE,sqlite3.SQLITE_DROP_TABLE) else sqlite3.SQLITE_OK)
        result = unresolved_snapshot(self.conn)
        self.assertEqual(result["metadata_only_or_unresolved_files"],7)
        self.assertEqual(sum(result["categories"].values()),7)
        self.assertEqual(result["categories"]["other_or_conflicting"],2)
        self.assertEqual(result["unknown_failure_code_candidate_rows"],1)
        self.assertNotIn("private code",json.dumps(result))
        self.assertEqual(result,unresolved_snapshot(self.conn))
    def test_exact_text_and_broad_service_predicate_are_separate(self):
        self.add("empty","Complete")
        self.add("false_positive","Review Required",extra={"other":{"status":"Complete"}})
        self.add("valid","Complete",text="retained text")
        self.add("compact","Complete",text="retained text",compact=True)
        result = unresolved_snapshot(self.conn)
        self.assertEqual(result["service_content_available_files"],3)
        self.assertEqual(result["exact_complete_with_nonempty_text_files"],2)
        self.assertEqual(result["service_complete_without_verified_text_files"],2)
        self.assertEqual(result["text_complete_not_counted_by_service_files"],1)
        self.assertEqual(result["metadata_only_or_unresolved_files"],1)
    def test_source_identity_dedup_and_fingerprint_drift(self):
        self.add("same","Retry Paused","IMAGE_RESOURCE_LIMIT")
        self.add("same","Retry Paused","IMAGE_RESOURCE_LIMIT")
        before = unresolved_snapshot(self.conn)
        self.assertEqual(before["represented_files"],1)
        self.assertEqual(before["unresolved_with_multiple_candidates"],1)
        self.assertEqual(before["failure_code_candidate_rows"]["IMAGE_RESOURCE_LIMIT"],2)
        self.conn.execute("UPDATE m365_knowledge_candidates SET source_sha256='changed' WHERE id=1")
        self.assertNotEqual(before["snapshot_sha256"],unresolved_snapshot(self.conn)["snapshot_sha256"])

if __name__ == "__main__":
    unittest.main()
