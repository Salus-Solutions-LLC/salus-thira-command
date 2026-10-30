"""Regression coverage for governed deterministic extraction review."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_retry_disposition as disposition


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "review.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY, classification_json TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,actor TEXT NOT NULL,detail_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        """)
        deterministic = {
            "extraction": {
                "status": "Automatic Retry Required",
                "failure_code": "PDF_ENCRYPTED",
            },
            "processing_flags": ["Automatic Extraction Retry Required", "Existing"],
        }
        retryable = {
            "extraction": {
                "status": "Automatic Retry Required",
                "failure_code": "IMAGE_RESOURCE_LIMIT",
            },
            "processing_flags": ["Automatic Extraction Retry Required"],
        }
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (1, json.dumps(deterministic)))
        conn.execute("INSERT INTO m365_knowledge_candidates VALUES(?,?)", (2, json.dumps(retryable)))
        result = disposition.reclassify(conn, {"PDF_ENCRYPTED": 1})
        assert result["reclassified"] == 1 and result["audit_events"] == 1, result
        assert result["review_required"] == 1 and result["retry_remaining"] == 1, result
        reviewed = json.loads(conn.execute(
            "SELECT classification_json FROM m365_knowledge_candidates WHERE id=1"
        ).fetchone()[0])
        retained = json.loads(conn.execute(
            "SELECT classification_json FROM m365_knowledge_candidates WHERE id=2"
        ).fetchone()[0])
        event = conn.execute(
            "SELECT event_type,detail_json FROM m365_knowledge_events"
        ).fetchone()
        conn.close()
        assert reviewed["extraction"]["status"] == disposition.REVIEW_STATUS, reviewed
        assert reviewed["extraction"]["retry_eligible"] is False, reviewed
        assert disposition.REVIEW_DISPOSITION in reviewed["processing_flags"], reviewed
        assert "Automatic Extraction Retry Required" not in reviewed["processing_flags"], reviewed
        assert retained["extraction"]["status"] == "Automatic Retry Required", retained
        assert event["event_type"] == "ExtractionRetryReclassifiedForGovernedReview", event
        assert json.loads(event["detail_json"])["failure_code"] == "PDF_ENCRYPTED", event
    print("KNOWLEDGE_RETRY_DISPOSITION_PASS")


if __name__ == "__main__":
    check()
