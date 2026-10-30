"""Content-free regression for the live Knowledge Library ledger probe."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_ledger_probe as probe


class Response:
    status_code = 200

    def __init__(self, value):
        self.value = value

    def json(self):
        return {"value": self.value}


def check_source_areas() -> None:
    root = "root-12345678"
    folders = {
        name: f"folder-{index:08d}"
        for index, name in enumerate(probe.SOURCE_AREAS, start=1)
    }
    files = {
        folders["10 Pending Classification"]: [("pending-00000001", "one.txt")],
        folders["90 Processed Intake"]: [("processed-000001", "two.txt")],
        folders["Does Not Upload"]: [("excluded-0000001", "three.txt")],
    }

    class Client:
        def get(self, url, **kwargs):
            folder_id = url.split("/items/", 1)[1].split("/children", 1)[0]
            if folder_id == root:
                return Response([
                    {"id": item_id, "name": name, "folder": {},
                     "parentReference": {"id": root}}
                    for name, item_id in folders.items()
                ])
            return Response([
                {"id": item_id, "name": name, "file": {}, "size": 10,
                 "eTag": '"v1"', "lastModifiedDateTime": "2026-10-29T00:00:00Z",
                 "parentReference": {"id": folder_id}}
                for item_id, name in files.get(folder_id, [])
            ])

    intake = SimpleNamespace(
        config=SimpleNamespace(drive_id="drive-12345678", folder_item_id=root),
        client=Client(), _headers=lambda: {},
    )
    original = probe.EXPECTED_BOUNDARY_FILES
    try:
        probe.EXPECTED_BOUNDARY_FILES = 3
        result = probe._source_area_reconciliation(
            intake, {"pending-00000001", "processed-000001", "historical-0001"}
        )
    finally:
        probe.EXPECTED_BOUNDARY_FILES = original
    assert result["area_pending_files"] == 1 and result["area_pending_gap"] == 0, result
    assert result["area_processed_files"] == 1 and result["area_processed_gap"] == 0, result
    assert result["area_does_not_upload_files"] == 1, result
    assert result["area_does_not_upload_gap"] == 1 and result["area_gap_total"] == 1, result
    assert result["represented_outside_boundary"] == 1, result


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
        CREATE TABLE m365_knowledge_holds(
          source_item_id TEXT NOT NULL,status TEXT NOT NULL,
          research_disposition TEXT NOT NULL,
          teaching_disposition TEXT NOT NULL,
          citation_disposition TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_extraction_checks(
          candidate_id INTEGER,attempts INTEGER,next_attempt INTEGER,last_code TEXT
        );
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
                ("four", "Automatic Retry Required", json.dumps({"extraction": {"status": "Automatic Retry Required", "failure_code": "DOCUMENT_PACKAGE_INVALID"}})),
                ("five", "Pending Review", "{}"),
            ],
        )
        conn.execute("INSERT INTO m365_bulk_cursors VALUES('delta','')")
        conn.execute(
            "INSERT INTO m365_knowledge_holds VALUES(?,?,?,?,?)",
            ("held", "Governed Hold", "Review Required", "Review Required", "Review Required"),
        )
        conn.execute("INSERT INTO m365_bulk_extraction_checks VALUES(1,1,0,'extraction_retry_required')")
        conn.execute("INSERT INTO m365_bulk_extraction_checks VALUES(2,6,9999999999,'archived_source_read_unavailable')")
        conn.execute("INSERT INTO m365_zip_jobs VALUES(1)")
        conn.execute("INSERT INTO m365_zip_member_index VALUES(1)")
        conn.execute("INSERT INTO m365_zip_member_index VALUES(2)")
        result = probe.collect(conn)
        conn.close()
        assert result["represented_distinct_files"] == 6, result
        assert result["represented_net_gap"] == 22_371, result
        assert result["unrepresented_files"] == 22_371, result
        assert result["bulk_rows"] == 5 and result["bulk_active_file_rows"] == 3, result
        assert result["bulk_open"] == 1 and result["bulk_oversize"] == 1, result
        assert result["candidate_rows"] == 3 and result["candidate_open"] == 2, result
        assert result["candidate_ingested_verified"] == 1, result
        assert result["extraction_complete"] == 1, result
        assert result["extraction_retry"] == 1 and result["extraction_missing"] == 1, result
        assert result["failure_document"] == 1 and result["failure_other"] == 0, result
        assert result["retry_attempts_1"] == 1 and result["retry_attempts_6_plus"] == 1, result
        assert result["retry_due"] == 1 and result["retry_backoff"] == 1, result
        assert result["retry_code_extraction"] == 1 and result["retry_code_archive_read"] == 1, result
        assert result["cursor_delta"] == 1 and result["cursor_errors"] == 0, result
        assert result["hold_rows"] == 1 and result["hold_active"] == 1, result
        assert result["hold_review_required"] == 1, result
        assert result["zip_jobs"] == 1 and result["zip_members"] == 2, result
    print("KNOWLEDGE_LEDGER_PROBE_PASS")


if __name__ == "__main__":
    check_source_areas()
    check()
