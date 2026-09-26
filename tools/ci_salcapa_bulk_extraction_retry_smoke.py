"""Archived extraction retries rotate, back off, and survive a new process."""

import hashlib
import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from salcapa_bulk_extraction_retry import process_due


def check():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, "retries.sqlite")
        def connect():
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            return conn
        conn = connect()
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates (
          id INTEGER PRIMARY KEY, source_name TEXT, source_sha256 TEXT,
          source_archive_item_id TEXT, classification_json TEXT, status TEXT);
        CREATE TABLE m365_knowledge_events (
          candidate_id INTEGER,event_type TEXT,actor TEXT,detail_json TEXT,created_at TEXT);
        """)
        content = b"verified original"
        sha = hashlib.sha256(content).hexdigest()
        pending = {"extraction": {"status": "Automatic Retry Required"},
                   "citation_metadata": {"source_mime_type": "text/plain"}}
        for i in range(1, 6):
            conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?)",
                         (i, f"{i}.txt", sha, f"archive-{i:08d}",
                          json.dumps(pending, sort_keys=True), "Ingested and Verified"))
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?)",
                     (6, "6.zip", sha, "archive-00000006",
                      json.dumps(pending, sort_keys=True), "Ingested and Verified"))
        conn.commit()
        seen = []
        class Writer:
            def verify_already_archived_source(self, item_id, expected, *, include_content):
                assert expected == sha and include_content
                seen.append(item_id)
                return {"content": content}
        def refresh(classification, document, expected):
            assert document.content == content and document.sha256 == expected
            assert document.mime_type == "text/plain"
            if document.name == "1.txt":
                return classification, "decoder_retry_required"
            updated = dict(classification)
            updated["extraction"] = {"status": "Complete", "text": "verified"}
            return updated, ""
        args = dict(get_writer=Writer, refresh=refresh,
                    failure_types=(RuntimeError,), now_iso=lambda: "2026-09-26T00:00:00Z",
                    skip_zip=True, limit=2)
        first = process_due(conn, clock=1000, **args)
        assert first == {"completed": 1, "retry": 1,
                         "codes": ["decoder_retry_required"]}, first
        conn.close()
        conn = connect()
        second = process_due(conn, clock=1001, **args)
        assert second["completed"] == 2 and second["retry"] == 0, second
        third = process_due(conn, clock=1002, **args)
        assert third["completed"] == 1 and third["retry"] == 0, third
        assert "archive-00000006" not in seen
        assert process_due(conn, clock=1059, **args)["retry"] == 0
        assert process_due(conn, clock=1060, **args)["retry"] == 1
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_events").fetchone()[0] == 4
        assert conn.execute("SELECT last_code,next_attempt FROM m365_bulk_extraction_checks "
                            "WHERE candidate_id=1").fetchone()["next_attempt"] == 1180
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_candidates WHERE "
                            "classification_json LIKE '%\"status\": \"Complete\"%'").fetchone()[0] == 4
        conn.close()
    print("bulk archived extraction retry smoke passed")


if __name__ == "__main__":
    check()
