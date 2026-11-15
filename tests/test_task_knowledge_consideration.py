import contextlib
import io
import json
import os
import sqlite3
import unittest

from salcapa_knowledge_consideration import _create_receipt_table, consider
from tools.live_task_knowledge_consideration import run_search


class TaskConsiderationTest(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
          CREATE TABLE m365_bulk_items(item_id TEXT,name TEXT,metadata_json TEXT,
            status TEXT,reason TEXT,kind TEXT,updated_at INTEGER);
          CREATE TABLE m365_knowledge_candidates(id INTEGER,source_item_id TEXT,
            source_name TEXT,source_relative_path TEXT,source_sha256 TEXT,
            source_modified_at TEXT,source_owner TEXT,status TEXT,target_folder TEXT,
            classification_json TEXT);
          CREATE TABLE m365_knowledge_holds(source_item_id TEXT,source_name TEXT,
            source_relative_path TEXT,source_area TEXT,hold_reason TEXT,status TEXT);
        """)
        for n, name in enumerate(("Knowledge source", "Conversation capture", "Held source", "Removed source")):
            self.conn.execute("INSERT INTO m365_bulk_items VALUES(?,?,?,?,?,?,?)",
                (str(n), name, "{}", "Removed" if n == 3 else "Done", "", "file", n))
        for n, identity in enumerate(("0", "1", "historical")):
            classification = {"extraction": {"status": "Pending" if identity == "1" else "Complete",
                "text": "" if identity == "1" else "Knowledge strategy evidence"}}
            self.conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
                (n, identity, "Conversation capture" if identity == "1" else "Knowledge source",
                 "Reference", "a" * 64, "2026-11-14", "Salus", "Candidate", "Reference",
                 json.dumps(classification)))
        self.conn.execute("INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?,?)",
            ("2", "Held source", "Restricted", "Hold", "unavailable", "Governed Hold"))
        _create_receipt_table(self.conn)
        self.conn.commit()
        self.previous = os.environ.get("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES")
        os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = "999"

    def tearDown(self):
        self.conn.close()
        if self.previous is None:
            os.environ.pop("SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES", None)
        else:
            os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"] = self.previous

    def run_task(self, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_search(self.conn, minimum_boundary=3, minimum_represented=4,
                queries=(("retrieval", "knowledge strategy"), ("capture", "conversation capture")), **kwargs)

    def test_live_boundary_history_holds_and_durable_receipts(self):
        summaries = self.run_task()
        self.assertEqual(len(summaries), 2)
        for row in summaries:
            self.assertEqual((row["boundary_files"], row["represented_files"], row["considered_files"]), (3, 4, 4))
            self.assertEqual(row["historical_additional_representations"], 1)
            self.assertEqual(row["content_available_files"], 2)
            self.assertEqual(row["metadata_only_or_unresolved_files"], 2)
            self.assertEqual(row["governed_hold_files"], 1)
        self.assertEqual([r["matched_files"] for r in summaries], [2, 1])
        self.assertEqual(os.environ["SALUS_KNOWLEDGE_MINIMUM_BOUNDARY_FILES"], "999")
        with self.assertRaisesRegex(RuntimeError, "already has receipts"):
            self.run_task()

    def test_durable_receipt_tampering_is_rejected(self):
        def corrupt(conn, *args):
            result = consider(conn, *args)
            conn.execute("UPDATE m365_knowledge_consideration_receipts SET considered_count=0")
            conn.commit()
            return result
        with self.assertRaisesRegex(RuntimeError, "Durable receipt"):
            self.run_task(consider_fn=corrupt)

    def test_same_count_membership_change_is_rejected(self):
        def change_membership(conn, *args):
            result = consider(conn, *args)
            conn.execute("UPDATE m365_bulk_items SET item_id='replacement' WHERE item_id='1'")
            conn.execute("UPDATE m365_knowledge_candidates SET source_item_id='replacement' WHERE source_item_id='1'")
            conn.commit()
            return result
        with self.assertRaisesRegex(RuntimeError, "membership changed"):
            self.run_task(consider_fn=change_membership)

    def test_access_expansion_is_rejected(self):
        def expand(conn, *args):
            result = consider(conn, *args)
            result["protected_member_access"] = True
            return result
        with self.assertRaisesRegex(RuntimeError, "authority boundary"):
            self.run_task(consider_fn=expand)

    def test_count_below_minimum_is_rejected(self):
        self.conn.execute("DELETE FROM m365_bulk_items WHERE item_id='2'")
        with self.assertRaisesRegex(RuntimeError, "below the governed minimum"):
            self.run_task()


if __name__ == "__main__":
    unittest.main()
