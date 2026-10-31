"""Regression coverage for bounded missing-source review routing."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tools import live_knowledge_candidate_reconcile as reconcile


ROOT = Path(__file__).resolve().parents[1]
JOB_NAME = "salcapa-cand-reconcile-b48224"


def check_azure_job_name_contract() -> None:
    assert 2 <= len(JOB_NAME) <= 32, len(JOB_NAME)
    assert JOB_NAME[0].isalpha() and JOB_NAME[-1].isalnum(), JOB_NAME
    assert JOB_NAME.replace("-", "").isalnum() and JOB_NAME == JOB_NAME.lower(), JOB_NAME
    workflow = (ROOT / ".github/workflows/salcapa-knowledge-candidate-reconcile.yml").read_text(
        encoding="utf-8"
    )
    bicep = (ROOT / "infra/azure/knowledge-candidate-reconcile-job.bicep").read_text(
        encoding="utf-8"
    )
    assert workflow.count(f"JOB_NAME={JOB_NAME}") == 2
    assert f"name: '{JOB_NAME}'" in bicep


def _insert_candidate(
    conn: sqlite3.Connection,
    candidate_id: int,
    status: str,
    rationale: str,
) -> None:
    conn.execute(
        "INSERT INTO m365_knowledge_candidates VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            candidate_id, "drive-12345678", f"item-{candidate_id:08d}", status,
            json.dumps({"extraction": {"status": "Complete"}}), rationale,
            "", "", "", "", "", "", "", "", "",
        ),
    )


def check() -> None:
    check_azure_job_name_contract()
    with tempfile.TemporaryDirectory() as directory:
        conn = sqlite3.connect(os.path.join(directory, "candidate-reconcile.sqlite"))
        conn.row_factory = sqlite3.Row
        conn.executescript("""
        CREATE TABLE m365_knowledge_candidates(
          id INTEGER PRIMARY KEY,source_drive_id TEXT NOT NULL,source_item_id TEXT NOT NULL,
          status TEXT NOT NULL,classification_json TEXT NOT NULL,review_rationale TEXT NOT NULL,
          destination_drive_id TEXT NOT NULL,destination_item_id TEXT NOT NULL,
          destination_web_url TEXT NOT NULL,destination_etag TEXT NOT NULL,
          source_archive_item_id TEXT NOT NULL,source_archive_web_url TEXT NOT NULL,
          source_archive_etag TEXT NOT NULL,source_archived_at TEXT NOT NULL,
          unused TEXT NOT NULL
        );
        CREATE TABLE m365_knowledge_events(
          id INTEGER PRIMARY KEY AUTOINCREMENT,candidate_id INTEGER NOT NULL,
          event_type TEXT NOT NULL,actor TEXT NOT NULL,detail_json TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE TABLE m365_bulk_items(drive_id TEXT NOT NULL,item_id TEXT NOT NULL);
        """)
        for candidate_id in range(1, 9):
            _insert_candidate(conn, candidate_id, "Pending Review", "Existing review")
        for candidate_id in range(9, 14):
            _insert_candidate(
                conn, candidate_id, "Automatic Retry Required",
                "Processed intake archive could not be verified",
            )
            conn.execute(
                "INSERT INTO m365_knowledge_events"
                "(candidate_id,event_type,actor,detail_json,created_at) VALUES(?,?,?,?,?)",
                (candidate_id, "AutomaticPromotionRetryScheduled", "test", "{}", "now"),
            )
        _insert_candidate(
            conn, 14, "Automatic Retry Required", "Destination write denied",
        )
        for candidate_id in range(15, 18):
            _insert_candidate(
                conn, candidate_id, "Approved for Promotion",
                "Automatically processed under policy.",
            )
        telemetry: list[tuple[str, str | int]] = []
        result = reconcile.reconcile(conn, lambda key, value: telemetry.append((key, value)))
        assert result["missing_sources_routed"] == 5, result
        assert result["audit_events"] == 5 and result["open_remaining"] == 17, result
        assert result["pending_review_total"] == 13, result
        assert result["automatic_retry_remaining"] == 1, result
        assert conn.execute(
            "SELECT status FROM m365_knowledge_candidates WHERE id=14"
        ).fetchone()[0] == "Automatic Retry Required"
        assert conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_candidates WHERE status='Pending Review'"
        ).fetchone()[0] == 13
        assert conn.execute(
            "SELECT COUNT(*) FROM m365_knowledge_events WHERE event_type=?",
            (reconcile.EVENT_TYPE,),
        ).fetchone()[0] == 5
        routed = conn.execute(
            "SELECT classification_json,review_rationale FROM m365_knowledge_candidates "
            "WHERE id=9"
        ).fetchone()
        classification = json.loads(routed["classification_json"])
        assert classification["source_reconciliation"] == {
            "status": "Review Required",
            "disposition": reconcile.DISPOSITION,
            "successor_match": "None",
            "boundary_files_rechecked": 22_377,
        }
        assert routed["review_rationale"] == "Processed intake archive could not be verified"
        assert ("pre_missing_count", 5) in telemetry, telemetry
        assert telemetry[-1] == ("stage", "committed"), telemetry
        conn.close()
    print("KNOWLEDGE_CANDIDATE_RECONCILE_PASS")


if __name__ == "__main__":
    check()
