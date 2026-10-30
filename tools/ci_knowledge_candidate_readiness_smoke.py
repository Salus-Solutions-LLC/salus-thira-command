"""Regression coverage for aggregate open-candidate readiness evidence."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_candidate_readiness as readiness


def check() -> None:
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "candidate-readiness.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,status TEXT NOT NULL,decision TEXT NOT NULL,
          target_folder TEXT NOT NULL,classification_json TEXT NOT NULL,
          destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
          destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
          source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
          source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL,
          review_rationale TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY,candidate_id INTEGER NOT NULL,event_type TEXT NOT NULL
        );
        """)
        fixtures = (
            (1, "Approved for Promotion", "Complete", "Automatically processed under policy."),
            (2, "Automatic Retry Required", "Review Required", "Knowledge destination could not be read"),
            (3, "Automatic Retry Required", "Retry Paused", "Knowledge upload did not complete"),
        )
        for candidate_id, status, extraction_status, rationale in fixtures:
            conn.execute(
                "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id, status, "Approved", "05 Research and Reference",
                    json.dumps({"extraction": {"status": extraction_status}}),
                    "", "", "", "", "", "", "", "", rationale,
                ),
            )
            conn.execute(
                "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
                (candidate_id, candidate_id, "AutomaticallyClassified"),
            )
        result = readiness.collect(conn, {
            "Pending Review": 0,
            "Approved for Promotion": 1,
            "Automatic Retry Required": 2,
            "Destination Verified": 0,
        })
        assert result["open_remaining"] == 3, result
        assert result["status_approved_for_promotion"] == 1, result
        assert result["status_automatic_retry_required"] == 2, result
        assert result["matrix_approved_for_promotion_complete"] == 1, result
        assert result["matrix_automatic_retry_required_review_required"] == 1, result
        assert result["matrix_automatic_retry_required_retry_paused"] == 1, result
        assert result["decision_approved"] == 3 and result["target_configured"] == 3, result
        assert result["destination_any"] == 0 and result["archive_any"] == 0, result
        assert result["rationale_policy"] == 1, result
        assert result["rationale_destination"] == 1, result
        assert result["rationale_upload"] == 1, result
        assert result["event_automaticallyclassified"] == 3, result
        assert result["content_downloads"] == 0 and result["rows_changed"] == 0, result
        conn.execute(
            "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                4, "Automatic Retry Required", "Approved", "05 Research and Reference",
                json.dumps({"extraction": {"status": "Complete"}}),
                "", "", "", "", "", "", "", "", "Automatically processed under policy.",
            ),
        )
        try:
            readiness.collect(conn, {
                "Pending Review": 0,
                "Approved for Promotion": 1,
                "Automatic Retry Required": 2,
                "Destination Verified": 0,
            })
            raise AssertionError("open-candidate scope growth was not rejected")
        except RuntimeError as error:
            assert "exceeded its approved boundary" in str(error), error
        conn.close()
    print("KNOWLEDGE_CANDIDATE_READINESS_PASS")


if __name__ == "__main__":
    check()
