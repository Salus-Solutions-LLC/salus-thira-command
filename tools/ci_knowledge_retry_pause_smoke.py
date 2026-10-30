"""Regression coverage for the governed automatic-retry pause."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_retry_pause as retry_pause


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "pause.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,classification_json TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_extraction_checks(
          candidate_id INTEGER PRIMARY KEY,attempts INTEGER NOT NULL,
          next_attempt INTEGER NOT NULL,lease_owner TEXT NOT NULL,
          lease_until INTEGER NOT NULL,last_code TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,actor TEXT NOT NULL,detail_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """)
        classification = {
            "extraction": {
                "status": retry_pause.PRIOR_STATUS,
                "failure_code": "PDF_RESOURCE_LIMIT",
            },
            "processing_flags": ["Automatic Extraction Retry Required", "Existing"],
        }
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (1, json.dumps(classification)))
        conn.execute(
            "INSERT INTO m365_bulk_extraction_checks VALUES(?,?,?,?,?,?)",
            (1, 7, 0, "", 0, "extraction_retry_required"),
        )
        result = retry_pause.pause(conn, {"PDF_RESOURCE_LIMIT": 1}, clock=1000)
        assert result["paused"] == 1 and result["retry_eligible"] == 1, result
        assert result["audit_events"] == 1 and result["automatic_remaining"] == 0, result
        row = conn.execute(
            "SELECT classification_json FROM m365_knowledge_candidates WHERE id=1"
        ).fetchone()
        paused = json.loads(row["classification_json"])
        assert paused["extraction"]["status"] == retry_pause.PAUSED_STATUS, paused
        assert paused["extraction"]["retry_eligible"] is True, paused
        assert paused["extraction"]["automatic_retry_paused"] is True, paused
        assert retry_pause.PAUSED_FLAG in paused["processing_flags"], paused
        assert "Automatic Extraction Retry Required" not in paused["processing_flags"], paused
        checkpoint = conn.execute(
            "SELECT attempts,next_attempt,last_code FROM m365_bulk_extraction_checks"
        ).fetchone()
        assert checkpoint["attempts"] == 7, checkpoint
        assert checkpoint["next_attempt"] == retry_pause.PAUSE_UNTIL, checkpoint
        assert checkpoint["last_code"] == "extraction_retry_required", checkpoint
        event = conn.execute(
            "SELECT event_type,detail_json FROM m365_knowledge_events"
        ).fetchone()
        assert event["event_type"] == "ExtractionAutomaticRetryPausedForProcessorRemediation", event
        assert json.loads(event["detail_json"])["resume_requires_governed_release"] is True, event

        active = {
            "extraction": {
                "status": retry_pause.PRIOR_STATUS,
                "failure_code": "PDF_SOURCE_LIMIT",
            },
            "processing_flags": ["Automatic Extraction Retry Required"],
        }
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (2, json.dumps(active)))
        conn.execute(
            "INSERT INTO m365_bulk_extraction_checks VALUES(?,?,?,?,?,?)",
            (2, 4, 0, "active-worker", 2000, "extraction_retry_required"),
        )
        try:
            retry_pause.pause(conn, {"PDF_SOURCE_LIMIT": 1}, clock=1000)
            raise AssertionError("active extraction lease was not rejected")
        except RuntimeError as error:
            assert "active extraction lease" in str(error), error
        unchanged = json.loads(conn.execute(
            "SELECT classification_json FROM m365_knowledge_candidates WHERE id=2"
        ).fetchone()[0])
        assert unchanged["extraction"]["status"] == retry_pause.PRIOR_STATUS, unchanged
        assert conn.execute("SELECT COUNT(*) FROM m365_knowledge_events").fetchone()[0] == 1
        conn.close()
    print("KNOWLEDGE_RETRY_PAUSE_PASS")


if __name__ == "__main__":
    check()
