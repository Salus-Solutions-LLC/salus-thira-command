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
    assert readiness.EXPECTED_INITIAL_STATUS_COUNTS == {
        "Pending Review": 8,
        "Approved for Promotion": 3,
        "Automatic Retry Required": 6,
        "Destination Verified": 0,
    }
    assert readiness.EXPECTED_PROMOTION_SCOPE_COUNTS == {
        "Approved for Promotion": 3,
        "Automatic Retry Required": 6,
    }
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
            (2, "Automatic Retry Required", "Complete", "Processed intake archive could not be verified"),
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
        conn.execute(
            "UPDATE m365_knowledge_candidates SET destination_drive_id='d',"
            "destination_item_id='i',destination_web_url='u',destination_etag='e',"
            "source_archive_item_id='a' WHERE id=2"
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (4, 2, "CandidateRoutedToGovernedExtractionReview"),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (5, 2, "AutomaticPromotionRetryScheduled"),
        )
        conn.execute(
            "INSERT INTO m365_knowledge_events VALUES(?,?,?)",
            (6, 2, "AutomaticallyPromotedVerifiedAndArchived"),
        )
        result = readiness.collect(
            conn,
            {
                "Pending Review": 0,
                "Approved for Promotion": 1,
                "Automatic Retry Required": 2,
                "Destination Verified": 0,
            },
            {
                "Approved for Promotion": 1,
                "Automatic Retry Required": 1,
            },
        )
        assert result["open_remaining"] == 3, result
        assert result["status_approved_for_promotion"] == 1, result
        assert result["status_automatic_retry_required"] == 2, result
        assert result["matrix_approved_for_promotion_complete"] == 1, result
        assert result["matrix_automatic_retry_required_complete"] == 1, result
        assert result["matrix_automatic_retry_required_retry_paused"] == 1, result
        assert result["decision_approved"] == 3 and result["target_configured"] == 3, result
        assert result["destination_any"] == 1 and result["destination_complete"] == 1, result
        assert result["archive_any"] == 1 and result["archive_complete"] == 0, result
        assert result["rationale_policy"] == 1, result
        assert result["rationale_archive"] == 1, result
        assert result["rationale_upload"] == 1, result
        assert result["event_automaticallyclassified"] == 3, result
        assert result["event_candidateroutedtogovernedextractionreview"] == 1, result
        assert result["event_automaticpromotionretryscheduled"] == 1, result
        assert result["promotion_scope_total"] == 2, result
        assert result["promotion_scope_fingerprint_groups"] == 2, result
        assert result[
            "promotion_fingerprint_approved_for_promotion_destination_none_"
            "archive_none_rationale_policy_promoted_absent_retry_absent"
        ] == 1, result
        assert result[
            "promotion_fingerprint_automatic_retry_required_destination_complete_"
            "archive_partial_rationale_archive_promoted_present_retry_present"
        ] == 1, result
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
            readiness.collect(
                conn,
                {
                    "Pending Review": 0,
                    "Approved for Promotion": 1,
                    "Automatic Retry Required": 2,
                    "Destination Verified": 0,
                },
                {
                    "Approved for Promotion": 1,
                    "Automatic Retry Required": 1,
                },
            )
            raise AssertionError("open-candidate scope growth was not rejected")
        except RuntimeError as error:
            assert "exceeded its approved boundary" in str(error), error
        conn.close()
    print("KNOWLEDGE_CANDIDATE_READINESS_PASS")


if __name__ == "__main__":
    check()
