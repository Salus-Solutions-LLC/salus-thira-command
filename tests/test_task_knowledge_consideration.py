import contextlib
import io
import json
import os
import sqlite3
import unittest
from types import SimpleNamespace

from salcapa_knowledge_consideration import _create_receipt_table, consider
from tools.live_task_knowledge_consideration import run_search, source_census


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
        census = kwargs.pop("source_census_fn", lambda: {str(n): ("v1", "2026-11-14") for n in range(3)})
        with contextlib.redirect_stdout(io.StringIO()):
            return run_search(self.conn, minimum_boundary=3, minimum_represented=4,
                source_census_fn=census,
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
        self.conn.execute("DELETE FROM m365_bulk_items WHERE item_id='0'")
        self.conn.execute("DELETE FROM m365_knowledge_candidates WHERE source_item_id='0'")
        with self.assertRaisesRegex(RuntimeError, "below the governed minimum"):
            self.run_task()

    def test_pending_work_subset_is_not_the_full_source_boundary(self):
        self.conn.execute("DELETE FROM m365_bulk_items WHERE item_id IN ('1','2')")
        rows = self.run_task()
        self.assertEqual(rows[0]["boundary_files"], 3)
        self.assertEqual(rows[0]["considered_files"], 4)

    def test_current_source_missing_from_all_representations_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "not fully represented"):
            self.run_task(source_census_fn=lambda: {"0": "v1", "1": "v1", "unrepresented": "v1"})
        self.assertEqual(self.conn.execute("SELECT COUNT(*) FROM m365_knowledge_consideration_receipts").fetchone()[0], 0)

    def test_current_source_version_drift_is_rejected(self):
        versions = iter(({str(n): "v1" for n in range(3)}, {str(n): "v2" for n in range(3)}))
        with self.assertRaisesRegex(RuntimeError, "versions changed"):
            self.run_task(source_census_fn=lambda: next(versions))


class SourceCensusTest(unittest.TestCase):
    def intake(self, payloads):
        queue = iter(payloads)
        class Client:
            def get(self, *_args, **_kwargs):
                return SimpleNamespace(status_code=200, json=lambda: next(queue))
        return SimpleNamespace(config=SimpleNamespace(drive_id="drive-0000", folder_item_id="folder-0000"),
            client=Client(), _headers=lambda: {})

    def root(self):
        return {"id": "folder-0000", "name": "SalCAPA Intake", "folder": {}}

    def file(self, version):
        return {"id": "source-0000", "file": {}, "eTag": version,
            "lastModifiedDateTime": "2026-11-14", "parentReference": {"driveId": "drive-0000"}}

    def test_all_pages_and_last_source_version_are_reconciled(self):
        endpoint = "https://graph.microsoft.com/v1.0/drives/drive-0000/items/folder-0000/delta"
        result = source_census(self.intake([self.root(),
            {"value": [self.file("v1")], "@odata.nextLink": endpoint + "?page=2"},
            {"value": [self.file("v2")], "@odata.deltaLink": endpoint + "?token=end"}]))
        self.assertEqual(result, {"source-0000": ("v2", "2026-11-14")})

    def test_foreign_continuation_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "authorized boundary"):
            source_census(self.intake([self.root(),
                {"value": [self.file("v1")], "@odata.nextLink": "https://example.com/?page=2"}]))

    def test_shortcut_is_rejected(self):
        endpoint = "https://graph.microsoft.com/v1.0/drives/drive-0000/items/folder-0000/delta"
        item = self.file("v1")
        item["remoteItem"] = {}
        with self.assertRaisesRegex(RuntimeError, "shortcut"):
            source_census(self.intake([self.root(), {"value": [item], "@odata.deltaLink": endpoint + "?token=end"}]))


if __name__ == "__main__":
    unittest.main()
