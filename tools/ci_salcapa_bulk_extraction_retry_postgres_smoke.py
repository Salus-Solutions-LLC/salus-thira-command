"""Verify the archived retry lease and update on the PostgreSQL adapter."""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from database import connect_database
from salcapa_bulk_extraction_retry import process_due


def check():
    assert os.getenv("SALUS_DB_BACKEND") == "postgres"
    conn = connect_database()
    content = b"verified original"
    sha = hashlib.sha256(content).hexdigest()
    try:
        conn.executescript("""
        CREATE TEMP TABLE m365_knowledge_candidates (
          id BIGINT PRIMARY KEY, source_name TEXT, source_sha256 TEXT,
          source_archive_item_id TEXT, classification_json TEXT, status TEXT);
        CREATE TEMP TABLE m365_knowledge_events (
          candidate_id BIGINT,event_type TEXT,actor TEXT,detail_json TEXT,created_at TEXT);
        """)
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?)",
                     (990001, "sample.txt", sha, "archive-990001",
                      json.dumps({"extraction": {"status": "Automatic Retry Required"}},
                                 sort_keys=True), "Ingested and Verified"))
        conn.commit()
        class Writer:
            def verify_already_archived_source(self, item_id, expected, *, include_content):
                assert item_id == "archive-990001" and expected == sha and include_content
                return {"content": content}
        def refresh(classification, document, expected):
            assert document.content == content and document.sha256 == expected
            updated = dict(classification)
            updated["extraction"] = {"status": "Complete"}
            return updated, ""
        result = process_due(conn, get_writer=Writer, refresh=refresh,
                             failure_types=(RuntimeError,),
                             now_iso=lambda: "2026-09-26T00:00:00Z", clock=1000)
        assert result["completed"] == 1 and result["retry"] == 0, result
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_events").fetchone()[0] == 1
    finally:
        conn.execute("DROP TABLE IF EXISTS m365_bulk_extraction_checks")
        conn.commit()
        conn.close()
    print("PostgreSQL bulk archived extraction retry smoke passed")


if __name__ == "__main__":
    check()
