"""Content-free regression for the live Knowledge Library ledger probe."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools.live_knowledge_ledger_probe import collect


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "ledger.sqlite")
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_bulk_cursors(
          phase TEXT NOT NULL,last_error TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE m365_bulk_items(
          item_id TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_candidates(
          source_item_id TEXT NOT NULL,status TEXT NOT NULL,
          classification_json TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_extraction_checks(id INTEGER);
        CREATE TABLE m365_zip_jobs(id INTEGER);
        CREATE TABLE m365_zip_member_index(id INTEGER);
        """)
        conn.executemany(
            "INSERT INTO m365_bulk_items VALUES(?,?,?)",
            [
                ("one", "file", "Done"),
                ("two", "file", "Pending"),
                ("three", "file", "Oversize"),
                ("folder", "folder", "Directory"),
                ("removed", "file", "Removed"),
            ],
        )
        conn.executemany(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?)",
            [
                ("one", "Ingested and Verified", json.dumps({"extraction": {"status": "Complete"}})),
                ("four", "Automatic Retry Required", json.dumps({"extraction": {"status": "Automatic Retry Required"}})),
                ("five", "Pending Review", "{}"),
            ],
        )
        conn.execute("INSERT INTO m365_bulk_cursors VALUES('delta','')")
        conn.execute("INSERT INTO m365_zip_jobs VALUES(1)")
        conn.execute("INSERT INTO m365_zip_member_index VALUES(1)")
        conn.execute("INSERT INTO m365_zip_member_index VALUES(2)")
        result = collect(conn)
        conn.close()
        assert result["represented_distinct_files"] == 5, result
        assert result["unrepresented_files"] == 22_372, result
        assert result["bulk_rows"] == 5 and result["bulk_active_file_rows"] == 3, result
        assert result["bulk_open"] == 1 and result["bulk_oversize"] == 1, result
        assert result["candidate_rows"] == 3 and result["candidate_open"] == 2, result
        assert result["candidate_ingested_verified"] == 1, result
        assert result["extraction_complete"] == 1, result
        assert result["extraction_retry"] == 1 and result["extraction_missing"] == 1, result
        assert result["cursor_delta"] == 1 and result["cursor_errors"] == 0, result
        assert result["zip_jobs"] == 1 and result["zip_members"] == 2, result
    print("KNOWLEDGE_LEDGER_PROBE_PASS")


if __name__ == "__main__":
    check()
